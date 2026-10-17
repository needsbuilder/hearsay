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
PKG_VERSION = re.compile(rf"`?(?P<pkg>{NAME})`?(?:==|@|\s+(?:to\s+|version\s+|to\s+version\s+)?)(?P<ver>{VERSION})\b")
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
CODE_SPAN = re.compile(r"`([^`\s]+)`")
DEPRECATED = re.compile(r"\b(?:is|has been|was)\s+deprecated\b", re.I)
FIX_WORDS = re.compile(r"\b(fix|fixes|fixed|patch|patches|patched|resolve[sd]?|address(?:es|ed)?|remediates?)\b", re.I)
AFFECTED_WORDS = re.compile(r"\b(vulnerable|affected|exposed)\b", re.I)

NOT_PACKAGES = {
    "to", "from", "version", "v", "python", "node", "nodejs", "node.js", "npm", "pip", "since", "in", "and",
    "or", "the", "of", "is", "at", "than", "release", "update", "upgrade", "upgrading", "bump", "bumped",
    "pin", "pinned", "with", "on", "by", "uses", "use", "using", "requires", "require", "version:", "v.",
    "cve", "ghsa", "typescript", "java", "go", "rust", "ruby", "php", "release:", "above", "below",
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


def _pairs(sentence: str) -> list[tuple[str, str]]:
    out = []
    for m in PKG_VERSION.finditer(sentence):
        pkg = m.group("pkg").strip("`")
        if pkg.lower() in NOT_PACKAGES or pkg[0].isdigit():
            continue
        out.append((pkg, m.group("ver").lstrip("v")))
    return out


def extract_with_patterns(text: str) -> tuple[list[Claim], ExtractionInfo]:
    sentences = split_sentences(text)
    doc_hint = _ecosystem_hint(text)
    claims: list[Claim] = []

    for s in sentences:
        eco = _ecosystem_hint(s) or doc_hint
        pairs = _pairs(s)
        used_pairs: set[tuple[str, str]] = set()

        for m in INSTALL.finditer(s):
            tool = m.group("tool").lower()
            install_eco = "npm" if tool in ("npm", "pnpm", "yarn") else "pypi"
            for arg in m.group("args").split():
                if arg.startswith("-") or arg in (".", "-e"):
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

        vulns = [v.upper() for v in VULN_ID.findall(s)]
        if vulns and pairs:
            pkg, ver = pairs[0]
            used_pairs.add((pkg, ver))
            if FIX_WORDS.search(s):
                kind = ClaimType.FIXES_VULNERABILITY
                verb = "fixes"
            elif AFFECTED_WORDS.search(s):
                kind = ClaimType.AFFECTED_BY_VULNERABILITY
                verb = "is affected by"
            else:
                kind = None
            if kind:
                for vid in vulns:
                    claims.append(_claim(kind, s, eco, package=pkg, version=ver, vulnerability_id=vid,
                                         statement=f"{pkg} {ver} {verb} {vid}."))

        lm = LICENSE.search(s)
        if lm:
            lic = (lm.group("a") or lm.group("b")).strip()
            candidates = [p for p, _ in pairs] or [c for c in CODE_SPAN.findall(s) if re.fullmatch(NAME, c)]
            if len(set(candidates)) == 1:
                claims.append(_claim(ClaimType.LICENSE_IS, s, eco, package=candidates[0], license=lic,
                                     statement=f"{candidates[0]} is licensed under {lic}."))

        if DEPRECATED.search(s) and eco == "npm":
            spans = [c for c in CODE_SPAN.findall(s) if re.fullmatch(NAME, c) and "." not in c and "(" not in c]
            if len(spans) == 1:
                claims.append(_claim(ClaimType.DEPRECATED, s, "npm", package=spans[0],
                                     statement=f"The npm package {spans[0]} is deprecated."))

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


def _claim(kind: ClaimType, sentence: str, eco: str | None, *, statement: str, **fields: str) -> Claim:
    return Claim(type=kind, statement=statement, source_sentence=sentence, ecosystem=eco, **fields)
