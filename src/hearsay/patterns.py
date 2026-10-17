"""Pattern-based claim extraction for --no-llm runs.

Best effort and deliberately narrow: it only finds the registry and advisory
shaped claims (install commands, pinned versions, vulnerability ids next to a
package and version, "licensed under" phrases, npm deprecations). Documentation
claims need the model extractor.
"""

from __future__ import annotations

import re

from .extract import dedupe, split_sentences
from .models import Claim, ClaimType, ExtractionInfo

VULN_ID = re.compile(
    r"\b(CVE-\d{4}-\d{4,7}|GHSA(?:-[23456789cfghjmpqrvwx]{4}){3}|PYSEC-\d{4}-\d+)\b", re.I
)
VERSION = r"v?\d+(?:\.\d+){1,3}(?:(?:a|b|rc|alpha|beta|pre|dev|post)[.\-]?\d*|-[0-9A-Za-z.\-]+)?"
NAME = r"@?[A-Za-z0-9][A-Za-z0-9_.\-]*(?:/[A-Za-z0-9_.\-]+)?"
PKG_VERSION = re.compile(rf"`?(?P<pkg>{NAME})`?(?P<sep>==|@|\s+(?:to\s+|version\s+|to\s+version\s+)?)(?P<ver>{VERSION})\b")
INSTALL = re.compile(
    r"\b(?P<tool>pip3?|uv pip|poetry|npm|pnpm|yarn)\s+(?:install|add|i)\s+(?P<args>[^\n;&|`]+)", re.I
)
LICENSE = re.compile(
    r"(?:licensed under(?: the)?|under the|released under(?: the)?)\s+"
    r"(?P<a>MIT|Apache(?:[- ]License)?[- ]?(?:v?2(?:\.0)?)?|BSD[- ]?[23][- ]?Clause|ISC|MPL[- ]?2\.0|"
    r"(?:L|A)?GPL[- ]?v?[23](?:\.[01])?|Unlicense)"
    r"|(?P<b>MIT|Apache[- ]2\.0|BSD[- ]3[- ]Clause|ISC|(?:L|A)?GPL[- ]?v?[23])[- ]licen[sc]ed",
    re.I,
)
# Dependabot and Renovate: "Bumps [urllib3](https://...) from 2.1.0 to 2.8.0"
BUMP = re.compile(
    rf"\bbump(?:s|ed)?\s+\[?`?(?P<pkg>{NAME})`?\]?(?:\([^)]*\))?\s+from\s+(?P<a>{VERSION})\s+to\s+(?P<b>{VERSION})",
    re.I,
)
CODE_SPAN = re.compile(r"`([^`\s]+)`")
DEPRECATED = re.compile(
    r"\b(?:(?:is|has been|was)(?:\s+(?:not|no longer|never))?|isn['\u2019]t|wasn['\u2019]t)\s+(deprecated)\b", re.I
)
FIX_WORDS = re.compile(r"\b(fix|fixes|fixed|patch|patches|patched|resolve[sd]?|address(?:es|ed)?|remediates?)\b", re.I)
AFFECTED_WORDS = re.compile(r"\b(vulnerable|affected|exposed)\b", re.I)

# Negation is read from the few words right before the word that decided the
# claim ("does not fix", "is no longer affected", "is not MIT licensed"), so a
# "not" in another clause does not flip the claim.
NEGATION_WINDOW = 4
_NEGATION_CUES = {"not", "never", "without"}


def negated_at(sentence: str, position: int) -> bool:
    words = re.findall(r"[\w'\u2019-]+", sentence[:position].lower())[-NEGATION_WINDOW:]
    if any(w in _NEGATION_CUES or w.endswith(("n't", "n\u2019t")) for w in words):
        return True
    return "no longer" in " ".join(words)

NOT_PACKAGES = {
    "to", "from", "version", "v", "python", "node", "nodejs", "node.js", "npm", "pip", "since", "in", "and",
    "or", "the", "of", "is", "at", "than", "release", "update", "upgrade", "upgrading", "bump", "bumped",
    "pin", "pinned", "with", "on", "by", "uses", "use", "using", "requires", "require", "version:", "v.",
    "cve", "ghsa", "typescript", "java", "go", "rust", "ruby", "php", "release:", "above", "below",
    "then", "first", "it", "them", "via", "for", "which", "that", "this", "if", "also", "now", "again",
    "instead", "fixes", "fix", "package", "packages", "library", "here", "there", "too",
}

# Words that end an install command's arguments: the sentence goes on in prose.
PROSE_STARTS = {
    "to", "for", "so", "which", "that", "then", "because", "since", "in", "on", "with", "from", "if",
    "when", "before", "after", "as", "into", "by", "via", "is", "was", "are", "it", "this", "fixes", "fix",
}


def _ecosystem_hint(text: str) -> str | None:
    t = text.lower()
    npm = any(w in t for w in ("npm", "package.json", "yarn", "pnpm", "node.js", "nodejs", "javascript", "typescript"))
    py = any(w in t for w in ("pip ", "pypi", "python", "requirements.txt", "pyproject", "uv add", "poetry"))
    if npm and not py:
        return "npm"
    if py and not npm:
        return "pypi"
    return None


def _pairs(sentence: str, *, pins_only: bool = False) -> list[tuple[str, str]]:
    out = []
    for m in PKG_VERSION.finditer(sentence):
        pkg = m.group("pkg").strip("`")
        if pkg.lower() in NOT_PACKAGES or pkg[0].isdigit():
            continue
        if pins_only and m.group("sep") not in ("==", "@"):
            continue
        out.append((pkg, m.group("ver").lstrip("v")))
    return out


def pinned_claims(text: str) -> list[Claim]:
    """Only the syntactic, unambiguous cases: install commands and pkg==1.2.3 / pkg@1.2.3 pins.

    Used next to the model extractor as a safety net for claims it skipped.
    """
    claims, _ = extract_with_patterns(text, pins_only=True)
    return claims


def extract_with_patterns(text: str, *, pins_only: bool = False) -> tuple[list[Claim], ExtractionInfo]:
    sentences = split_sentences(text)
    doc_hint = _ecosystem_hint(text)
    claims: list[Claim] = []

    for s in sentences:
        eco = _ecosystem_hint(s) or doc_hint
        pairs = _pairs(s, pins_only=pins_only)
        used_pairs: set[tuple[str, str]] = set()

        for m in INSTALL.finditer(s):
            tool = m.group("tool").lower()
            install_eco = "npm" if tool in ("npm", "pnpm", "yarn") else "pypi"
            # Arguments end where the prose starts again: "pip install x==1.0, which fixes ..."
            args = re.split(r"[,;()]|\.(?:\s|$)|\s-\s", m.group("args"))[0]
            for arg in args.split():
                if arg.lower() in PROSE_STARTS:  # "pip install x to get the new router"
                    break
                if arg.startswith("-") or arg in (".", "-e") or arg.lower() in NOT_PACKAGES:
                    continue
                pm = re.fullmatch(rf"(?P<pkg>{NAME})(?:==|@)(?P<ver>{VERSION})", arg)
                if pm:
                    pkg, ver = pm.group("pkg"), pm.group("ver")
                    used_pairs.add((pkg, ver))
                    claims.append(_claim(ClaimType.VERSION_EXISTS, s, install_eco, package=pkg, version=ver,
                                         statement=f"{pkg} {ver} is published on {_reg(install_eco)}."))
                elif re.fullmatch(NAME, arg):
                    claims.append(_claim(ClaimType.PACKAGE_EXISTS, s, install_eco, package=arg,
                                         statement=f"{arg} is a package on {_reg(install_eco)}."))

        for m in BUMP.finditer(s):
            pkg = m.group("pkg")
            for ver in (m.group("a").lstrip("v"), m.group("b").lstrip("v")):
                if (pkg, ver) in used_pairs:
                    continue
                used_pairs.add((pkg, ver))
                claims.append(_claim(ClaimType.VERSION_EXISTS, s, eco, package=pkg, version=ver,
                                     statement=f"{pkg} {ver} is a published release."))

        if pins_only:
            for pkg, ver in pairs:
                if (pkg, ver) not in used_pairs:
                    claims.append(_claim(ClaimType.VERSION_EXISTS, s, eco, package=pkg, version=ver,
                                         statement=f"{pkg} {ver} is a published release."))
            continue

        vulns = [v.upper() for v in VULN_ID.findall(s)]
        if vulns and pairs:
            pkg, ver = pairs[0]
            used_pairs.add((pkg, ver))
            fix, hit = FIX_WORDS.search(s), AFFECTED_WORDS.search(s)
            if fix:
                kind, verb, neg_verb, word = ClaimType.FIXES_VULNERABILITY, "fixes", "does not fix", fix
            elif hit:
                kind, verb, neg_verb, word = ClaimType.AFFECTED_BY_VULNERABILITY, "is affected by", "is not affected by", hit
            else:
                kind = None
            if kind:
                negated = negated_at(s, word.start())
                for vid in vulns:
                    claims.append(_claim(kind, s, eco, package=pkg, version=ver, vulnerability_id=vid, negated=negated,
                                         statement=f"{pkg} {ver} {neg_verb if negated else verb} {vid}."))

        lm = LICENSE.search(s)
        if lm:
            lic = (lm.group("a") or lm.group("b")).strip()
            candidates = [p for p, _ in pairs] or [c for c in CODE_SPAN.findall(s) if re.fullmatch(NAME, c)]
            if len(set(candidates)) == 1:
                negated = negated_at(s, lm.start())
                claims.append(_claim(ClaimType.LICENSE_IS, s, eco, package=candidates[0], license=lic, negated=negated,
                                     statement=f"{candidates[0]} is {'not ' if negated else ''}licensed under {lic}."))

        dm = DEPRECATED.search(s)
        if dm and eco == "npm":
            spans = [c for c in CODE_SPAN.findall(s) if re.fullmatch(NAME, c) and "." not in c and "(" not in c]
            if len(spans) == 1:
                negated = negated_at(s, dm.start(1))
                claims.append(_claim(ClaimType.DEPRECATED, s, "npm", package=spans[0], negated=negated,
                                     statement=f"The npm package {spans[0]} is {'not ' if negated else ''}deprecated."))

        for pkg, ver in pairs:
            if (pkg, ver) not in used_pairs:
                claims.append(_claim(ClaimType.VERSION_EXISTS, s, eco, package=pkg, version=ver,
                                     statement=f"{pkg} {ver} is a published release."))

    claims = dedupe(claims)
    for i, c in enumerate(claims, 1):
        c.id = f"c{i}"
    return claims, ExtractionInfo(method="patterns", sentences=len(sentences))


def _reg(eco: str | None) -> str:
    return {"pypi": "PyPI", "npm": "npm"}.get(eco or "", "its registry")


def _claim(
    kind: ClaimType, sentence: str, eco: str | None, *, statement: str, negated: bool = False, **fields: str
) -> Claim:
    return Claim(
        type=kind, statement=statement, source_sentence=sentence, ecosystem=eco, origin="pattern", negated=negated, **fields
    )
