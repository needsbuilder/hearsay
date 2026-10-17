"""Pick the few passages of documentation the jury will read.

Tavily Extract already returns the page chunks it ranks highest for the
claim. Here they are split into paragraphs, scored by how many of the
claim's terms they contain (identifiers count more), and the best ones are
kept under a character budget so small models see a short context.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from .models import Claim, Passage

STOPWORDS = set(
    """a an and are as at be been but by can could did do does for from has have how if in into is it its
    may might must not of on or should since so such than that the their then there these this those to
    was were what when where which while who will with would you your accept accepts accepted argument
    arguments parameter parameters option options support supports supported official documentation docs""".split()
)

MAX_PASSAGE_CHARS = 900
DEFAULT_TOTAL_CHARS = 4500
DEFAULT_MAX_PASSAGES = 6


def _identifier_parts(text: str) -> list[str]:
    return [p for p in re.split(r"[^A-Za-z0-9_]+", text) if len(p) >= 2]


def claim_terms(claim: Claim) -> dict[str, float]:
    """Lowercased search terms with weights. Exact identifiers weigh most."""
    terms: dict[str, float] = {}

    def add(term: str, weight: float) -> None:
        t = term.lower().strip()
        if len(t) < 2 or t in STOPWORDS:
            return
        terms[t] = max(terms.get(t, 0.0), weight)

    if claim.parameter:
        add(claim.parameter.strip("`"), 4.0)
    if claim.symbol:
        parts = _identifier_parts(claim.symbol)
        for p in parts:
            add(p, 2.0)
        if parts:
            add(parts[-1], 3.0)
    for name in (claim.package, claim.vulnerability_id, claim.since_version, claim.license):
        if name:
            add(name, 2.0)
    for word in re.findall(r"[A-Za-z0-9_]+(?:\.[A-Za-z0-9_]+)*", claim.statement):
        add(word, 1.0)
    return terms


def split_passages(text: str) -> list[str]:
    """Paragraph-sized pieces of a page, each at most MAX_PASSAGE_CHARS."""
    pieces: list[str] = []
    for chunk in re.split(r"\s*\[\.\.\.\]\s*", text):  # Tavily joins ranked chunks with [...]
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", chunk) if p.strip()]
        buf = ""
        for para in paragraphs:
            if len(para) > MAX_PASSAGE_CHARS:
                if buf:
                    pieces.append(buf)
                    buf = ""
                pieces.extend(_split_long(para))
                continue
            if buf and len(buf) + len(para) + 2 > MAX_PASSAGE_CHARS:
                pieces.append(buf)
                buf = ""
            buf = f"{buf}\n\n{para}" if buf else para
        if buf:
            pieces.append(buf)
    return [p for p in pieces if len(p) >= 20]


def _split_long(para: str) -> list[str]:
    out, buf = [], ""
    for line in re.split(r"(?<=[.!?])\s+|\n", para):
        if buf and len(buf) + len(line) + 1 > MAX_PASSAGE_CHARS:
            out.append(buf)
            buf = ""
        if len(line) > MAX_PASSAGE_CHARS:
            out.extend(line[i : i + MAX_PASSAGE_CHARS] for i in range(0, len(line), MAX_PASSAGE_CHARS))
            continue
        buf = f"{buf} {line}".strip() if buf else line
    if buf:
        out.append(buf)
    return out


@dataclass
class _Scored:
    score: float
    order: int
    url: str
    title: str
    text: str


def score(text: str, terms: dict[str, float]) -> float:
    lower = text.lower()
    total = 0.0
    for term, weight in terms.items():
        if re.fullmatch(r"[a-z0-9_]+", term):
            hits = len(re.findall(rf"(?<![a-z0-9_]){re.escape(term)}(?![a-z0-9_])", lower))
        else:
            hits = lower.count(term)
        if hits:
            total += weight * (1.0 + math.log(min(hits, 5)))
    return total


def select_passages(
    pages: list[tuple[str, str, str]],
    claim: Claim,
    *,
    max_passages: int = DEFAULT_MAX_PASSAGES,
    max_chars: int = DEFAULT_TOTAL_CHARS,
) -> list[Passage]:
    """pages: (url, title, text). Returns numbered passages, best first."""
    terms = claim_terms(claim)
    scored: list[_Scored] = []
    seen: set[str] = set()
    order = 0
    for url, title, text in pages:
        for piece in split_passages(text):
            key = " ".join(piece.split()).lower()
            if key in seen:
                continue
            seen.add(key)
            scored.append(_Scored(score(piece, terms), order, url, title, piece))
            order += 1
    scored.sort(key=lambda s: (-s.score, s.order))
    chosen: list[_Scored] = []
    used = 0
    for s in scored:
        if s.score <= 0 or len(chosen) >= max_passages:
            break
        if used + len(s.text) > max_chars and chosen:
            continue
        chosen.append(s)
        used += len(s.text)
    return [Passage(id=i, url=s.url, title=s.title, text=s.text) for i, s in enumerate(chosen, 1)]
