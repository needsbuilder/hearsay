"""Claim extraction with a language model.

The input is split into numbered sentences. The model returns claims that
point at sentence numbers, so the source sentence attached to each claim is
always copied from the input by Hearsay, never retyped by the model. Every
value the model fills in (package, version, ids, parameter) must appear in
those sentences, otherwise the claim is rejected.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from pydantic import ValidationError

from .llm import ChatModel, LLMError, parse_json_object
from .models import CLAIM_FIELDS, Claim, ClaimType, ExtractionInfo, RejectedClaim

MAX_CHUNK_CHARS = 2500

_SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9`\"'(\[*_])")
_FENCE_LINE = re.compile(r"^\s*(```|~~~)")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences, one code line per unit inside fenced blocks.

    Every returned unit is a verbatim substring of the input.
    """
    units: list[str] = []
    in_code = False
    for line in text.splitlines():
        if _FENCE_LINE.match(line):
            in_code = not in_code
            continue
        stripped = line.strip()
        if not stripped:
            continue
        if in_code:
            units.append(stripped)
            continue
        for part in _SENTENCE_BREAK.split(stripped):
            part = part.strip()
            if len(part) >= 3:
                units.append(part)
    return units


def chunk_sentences(sentences: list[str], limit: int = MAX_CHUNK_CHARS) -> list[list[int]]:
    """Group sentence indexes into chunks of at most `limit` characters."""
    chunks: list[list[int]] = []
    current: list[int] = []
    size = 0
    for i, s in enumerate(sentences):
        if current and size + len(s) > limit:
            chunks.append(current)
            current, size = [], 0
        current.append(i)
        size += len(s) + 6
    if current:
        chunks.append(current)
    return chunks


SYSTEM_PROMPT = """You extract checkable claims about third-party facts from text written by a coding agent (pull request descriptions, chat answers, code comments).

Extract a claim when a sentence states a fact about the outside world that a primary source could confirm: a package on PyPI or npm, a release version, a vulnerability (CVE, GHSA), a licence, a deprecation or removal, a documented API parameter, or what a library, language or vendor API does.
Skip: statements about the author's own work or code ("tests pass", "I refactored X", "this PR adds Y"), opinions, plans, questions and instructions.

Claim types and the fields each one needs:
- package_exists: package
- version_exists: package, version
- fixes_vulnerability: package, version, vulnerability_id  (that version contains the fix)
- affected_by_vulnerability: package, version, optional vulnerability_id
- license_is: package, license
- deprecated: symbol or package, optional since_version  (deprecated or removed)
- parameter_exists: symbol, parameter  (a function or API documents this parameter/option)
- api_behavior: subject (library, language or vendor API), optional symbol  (what it does)
- other_external: any other checkable external fact

Return a JSON object {"claims": [...]}. Each claim has exactly these keys:
"type", "sentences" (list of sentence numbers it comes from), "statement" (the claim as one short standalone sentence), "ecosystem" ("pypi", "npm", another registry name, or null), "package", "version", "vulnerability_id", "license", "symbol", "parameter", "since_version", "subject", "negated" (true only if the sentence says the fact is NOT the case).
Copy names, versions and ids exactly as written in the sentence. Use null for anything the sentence does not say; never guess. The ecosystem may be inferred from context (pip, Python -> "pypi"; npm, Node.js, JavaScript -> "npm").
Split a sentence that states several facts into several claims. If there are no claims, return {"claims": []}."""

EXAMPLE_INPUT = """[1] Bumped urllib3 to 2.2.2, which fixes CVE-2024-37891.
[2] I also cleaned up the retry helper and all tests pass.
[3] Note that `datetime.utcnow()` is deprecated since Python 3.12, and `json.dumps` accepts a `sort_keys` argument."""

EXAMPLE_OUTPUT = {
    "claims": [
        {"type": "fixes_vulnerability", "sentences": [1], "statement": "urllib3 2.2.2 fixes CVE-2024-37891.",
         "ecosystem": "pypi", "package": "urllib3", "version": "2.2.2", "vulnerability_id": "CVE-2024-37891",
         "license": None, "symbol": None, "parameter": None, "since_version": None, "subject": None, "negated": False},
        {"type": "deprecated", "sentences": [3], "statement": "datetime.utcnow() is deprecated since Python 3.12.",
         "ecosystem": None, "package": None, "version": None, "vulnerability_id": None, "license": None,
         "symbol": "datetime.utcnow()", "parameter": None, "since_version": "3.12", "subject": "Python", "negated": False},
        {"type": "parameter_exists", "sentences": [3], "statement": "json.dumps accepts a sort_keys argument.",
         "ecosystem": None, "package": None, "version": None, "vulnerability_id": None, "license": None,
         "symbol": "json.dumps", "parameter": "sort_keys", "since_version": None, "subject": "Python", "negated": False},
    ]
}


def build_messages(numbered: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "Sentences:\n" + EXAMPLE_INPUT},
        {"role": "assistant", "content": json.dumps(EXAMPLE_OUTPUT)},
        {"role": "user", "content": "Sentences:\n" + numbered},
    ]


# ---------------------------------------------------------------- validation

_ALNUM = re.compile(r"[^a-z0-9]+")


def _squash(text: str) -> str:
    return _ALNUM.sub("", text.lower())


def _grounded(value: str, sentence: str) -> bool:
    v = _squash(value)
    return bool(v) and v in _squash(sentence)


def _symbol_grounded(symbol: str, sentence: str) -> bool:
    parts = [p for p in re.split(r"[.:()\[\]\s/#]+", symbol) if p]
    return bool(parts) and _grounded(parts[-1], sentence)


def _license_grounded(license_name: str, sentence: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+", sentence.lower()))
    tokens = [t for t in re.findall(r"[a-z]+", license_name.lower()) if t not in {"license", "licence"}]
    return bool(tokens) and tokens[0] in words or _grounded(license_name, sentence)


GROUNDED_FIELDS = ("package", "version", "vulnerability_id", "parameter", "since_version")


@dataclass
class ParsedClaims:
    claims: list[Claim] = field(default_factory=list)
    rejected: list[RejectedClaim] = field(default_factory=list)


def parse_claims(data: dict, sentences: list[str], index_map: dict[int, int]) -> ParsedClaims:
    """Validate the model's JSON strictly. `index_map` maps shown numbers to sentence indexes."""
    if set(data.keys()) != {"claims"} or not isinstance(data["claims"], list):
        raise ValueError('expected an object with exactly one key, "claims", holding a list')
    out = ParsedClaims()
    allowed = {"type", "sentences", "statement", "negated", *CLAIM_FIELDS}
    for raw in data["claims"]:
        errors: list[str] = []
        if not isinstance(raw, dict):
            out.rejected.append(RejectedClaim(raw=str(raw), errors=["claim is not an object"]))
            continue
        extra = set(raw) - allowed
        if extra:
            errors.append(f"unknown keys: {sorted(extra)}")
        nums = raw.get("sentences")
        if isinstance(nums, int):
            nums = [nums]
        if not isinstance(nums, list) or not nums or not all(isinstance(n, int) and n in index_map for n in nums):
            errors.append(f"sentences must list sentence numbers from the input, got {nums!r}")
            out.rejected.append(RejectedClaim(raw=raw, errors=errors))
            continue
        source = " ".join(sentences[index_map[n]] for n in sorted(set(nums)))
        fields = {k: raw.get(k) for k in CLAIM_FIELDS}
        for k, v in fields.items():
            if v is not None and not isinstance(v, str):
                errors.append(f"{k} must be a string or null")
            elif isinstance(v, str) and not v.strip():
                fields[k] = None
        if errors:
            out.rejected.append(RejectedClaim(raw=raw, errors=errors))
            continue
        try:
            claim = Claim(
                type=raw.get("type"),
                statement=raw.get("statement") or "",
                source_sentence=source,
                negated=bool(raw.get("negated") or False),
                **{k: (v.strip() if isinstance(v, str) else v) for k, v in fields.items()},
            )
        except ValidationError as exc:
            out.rejected.append(RejectedClaim(raw=raw, errors=[e["msg"] + f" ({'.'.join(map(str, e['loc']))})" for e in exc.errors()]))
            continue
        missing = claim.missing_fields()
        if missing:
            errors.append(f"{claim.type.value} needs: {', '.join(missing)}")
        for name in GROUNDED_FIELDS:
            value = getattr(claim, name)
            if value and not _grounded(value, source):
                errors.append(f"{name} {value!r} does not appear in the sentence")
        if claim.symbol and not _symbol_grounded(claim.symbol, source):
            errors.append(f"symbol {claim.symbol!r} does not appear in the sentence")
        if claim.license and not _license_grounded(claim.license, source):
            errors.append(f"license {claim.license!r} does not appear in the sentence")
        if errors:
            out.rejected.append(RejectedClaim(raw=raw, errors=errors))
            continue
        out.claims.append(claim)
    return out


def _claim_key(c: Claim) -> tuple:
    return (
        c.type.value,
        *(_squash(getattr(c, f) or "") for f in ("package", "version", "vulnerability_id", "license", "symbol", "parameter")),
        c.negated,
        _squash(c.statement) if c.type in (ClaimType.API_BEHAVIOR, ClaimType.OTHER_EXTERNAL) else "",
    )


def dedupe(claims: list[Claim]) -> list[Claim]:
    seen: set[tuple] = set()
    out = []
    for c in claims:
        k = _claim_key(c)
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def extract_claims(llm: ChatModel, model: str, text: str) -> tuple[list[Claim], ExtractionInfo]:
    sentences = split_sentences(text)
    info = ExtractionInfo(method="llm", model=model, sentences=len(sentences))
    claims: list[Claim] = []
    for chunk in chunk_sentences(sentences):
        index_map = {n + 1: idx for n, idx in enumerate(chunk)}
        numbered = "\n".join(f"[{n}] {sentences[idx]}" for n, idx in index_map.items())
        messages = build_messages(numbered)
        try:
            parsed = _extract_chunk(llm, model, messages, sentences, index_map, info)
        except LLMError as exc:
            info.errors.append(str(exc))
            continue
        if parsed:
            claims.extend(parsed.claims)
            info.rejected.extend(parsed.rejected)
    claims = dedupe(claims)
    for i, c in enumerate(claims, 1):
        c.id = f"c{i}"
    return claims, info


def _extract_chunk(
    llm: ChatModel,
    model: str,
    messages: list[dict[str, str]],
    sentences: list[str],
    index_map: dict[int, int],
    info: ExtractionInfo,
) -> ParsedClaims | None:
    """One attempt, and one repair round if anything was invalid."""
    reply = llm.complete(model, messages)
    first: ParsedClaims | None = None
    problem: str
    try:
        first = parse_claims(parse_json_object(reply), sentences, index_map)
        if not first.rejected:
            return first
        problem = "; ".join(
            f"claim {json.dumps(r.raw)[:160]}: {', '.join(r.errors)}" for r in first.rejected
        )
    except ValueError as exc:
        problem = str(exc)
    info.errors.append(f"attempt 1 invalid: {problem[:500]}")

    repair = messages + [
        {"role": "assistant", "content": reply},
        {
            "role": "user",
            "content": f"Some of your output was invalid: {problem[:1500]}\n"
            "Return the complete corrected JSON object. Copy values exactly from the sentences, use null "
            "when a sentence does not state a value, and drop a claim rather than guess.",
        },
    ]
    reply2 = llm.complete(model, repair)
    try:
        second = parse_claims(parse_json_object(reply2), sentences, index_map)
    except ValueError as exc:
        info.errors.append(f"attempt 2 invalid: {str(exc)[:500]}")
        return first
    if second.rejected:
        info.errors.append(f"attempt 2 still had {len(second.rejected)} invalid claims; they were dropped")
    return second
