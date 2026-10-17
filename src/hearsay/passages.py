"""Pick the few passages of documentation the jury will read.

Tavily Extract returns whole pages as Markdown. Each page is cut into
sections by its headings (Markdown headings and Sphinx definitions such as
`classmethod datetime.utcnow()`), so every window of text keeps its heading
path. Windows are scored by how many of the claim's terms they contain
(identifiers count more, and windows about the claim's symbol count most),
and the best ones are kept under a character budget so small models see a
short context.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .models import Claim, Passage
from .quotes import normalize

if TYPE_CHECKING:
    from .anchoring import Anchor

STOPWORDS = set(
    """a an and are as at be been but by can could did do does for from has have how if in into is it its
    may might must not of on or should since so such than that the their then there these this those to
    was were what when where which while who will with would you your accept accepts accepted argument
    arguments parameter parameters option options support supports supported official documentation docs""".split()
)

MAX_PASSAGE_CHARS = 900
ANCHOR_BONUS = 10.0
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
    """Paragraph-sized pieces of a page, each at most MAX_PASSAGE_CHARS.

    Headings and short lead-in lines stay attached to the paragraph after
    them; other paragraphs are not packed together, so an unrelated
    paragraph never rides along with a relevant one.
    """
    pieces: list[str] = []
    for chunk in re.split(r"\s*\[\.\.\.\]\s*", text):  # Tavily joins ranked chunks with [...]
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", chunk) if p.strip()]
        lead = ""
        for para in paragraphs:
            if _is_lead_in(para):
                lead = f"{lead}\n\n{para}" if lead else para
                continue
            body = f"{lead}\n\n{para}" if lead else para
            lead = ""
            if len(body) > MAX_PASSAGE_CHARS:
                pieces.extend(_split_long(body))
            else:
                pieces.append(body)
        if lead:
            pieces.append(lead)
    return [p for p in pieces if len(p) >= 20]


def _is_lead_in(para: str) -> bool:
    return para.startswith("#") or (len(para) < 80 and "\n" not in para)


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


# ---------------------------------------------------------------- page structure

_ATX = re.compile(r"^(#{1,6})\s+(.*?)\s*$")
# Sphinx definition terms: "*classmethod* datetime.utcnow()[\u00b6](#datetime.datetime.utcnow "Link to this definition")"
_DEFINITION = re.compile(r'^(\s*)(.+?)\[\u00b6\]\(#([^)\s]+)\s+"Link to this definition"\)\s*$')
_PERMALINK = re.compile(r'\[(?:#|\u00b6)\]\(#[^)]*\)')
DEFINITION_LEVEL = 7  # below every Markdown heading


@dataclass
class Heading:
    text: str
    level: int
    api: bool
    indent: int = 0
    raw: str = ""  # the heading's line as it appears in the page (trim.py re-emits it)


def clean_heading(raw: str) -> str:
    return normalize(_PERMALINK.sub("", raw)).rstrip("\u00b6#").strip()


def page_sections(text: str) -> list[tuple[list[Heading], str]]:
    """(heading path, body) for every stretch of text between headings."""
    from .anchoring import is_api_heading

    stack: list[Heading] = []
    buf: list[str] = []
    out: list[tuple[list[Heading], str]] = []

    def flush() -> None:
        body = "\n".join(buf).strip()
        if body:
            out.append((list(stack), body))
        buf.clear()

    for line in text.splitlines():
        m = _ATX.match(line)
        if m:
            flush()
            level = len(m.group(1))
            while stack and stack[-1].level >= level:
                stack.pop()
            title = clean_heading(m.group(2))
            stack.append(Heading(title, level, api=is_api_heading(title), raw=line))
            continue
        d = _DEFINITION.match(line)
        if d:
            flush()
            indent = len(d.group(1).expandtabs())
            level = DEFINITION_LEVEL + indent // 2
            while stack and stack[-1].level >= level:
                stack.pop()
            term, target = clean_heading(d.group(2)), d.group(3)
            if "." in target and target not in term:
                term = f"{term} [{target}]"  # the qualified name Sphinx gives the definition
            stack.append(Heading(term, level, api=True, indent=indent, raw=line))
            continue
        if line.strip() and stack and stack[-1].level >= DEFINITION_LEVEL:
            # A definition's body is its ":" line and the lines indented under it.
            indent = len(line) - len(line.lstrip())
            stripped = line.lstrip()
            while stack and stack[-1].level >= DEFINITION_LEVEL and indent <= stack[-1].indent and not stripped.startswith(":"):
                flush()
                stack.pop()
        buf.append(line)
    flush()
    return out


@dataclass
class Window:
    url: str
    title: str
    section: list[str]
    api_heading: str | None
    text: str
    order: int = 0
    score: float = 0.0
    anchored: bool = field(default=False)
    headings: list[Heading] = field(default_factory=list, repr=False)
    body: str = field(default="", repr=False)  # the whole section body this window came from

    def as_passage(self, pid: int) -> Passage:
        return Passage(id=pid, url=self.url, title=self.title, section=self.section, api_heading=self.api_heading, text=self.text)


def page_windows(url: str, title: str, text: str) -> list[Window]:
    windows = []
    for headings, body in page_sections(text):
        section = [h.text for h in headings]
        api = next((h.text for h in reversed(headings) if h.api), None)
        for piece in split_passages(body):
            windows.append(Window(url, title, section, api, piece, headings=headings, body=body))
    return windows


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
    anchor: "Anchor | None" = None,
    max_passages: int = DEFAULT_MAX_PASSAGES,
    max_chars: int = DEFAULT_TOTAL_CHARS,
) -> list[Passage]:
    """pages: (url, title, markdown). Returns numbered passages, best first.

    With an anchor, windows about the claim's symbol (see anchoring.py) rank
    above windows that merely share its words.
    """
    terms = claim_terms(claim)
    windows: list[Window] = []
    seen: set[tuple[str, str]] = set()
    for url, title, text in pages:
        for w in page_windows(url, title, text):
            key = (" > ".join(w.section), " ".join(w.text.split()).lower())
            if key in seen:
                continue
            seen.add(key)
            w.order = len(windows)
            base = score(w.text, terms) + 0.5 * score(" ".join(w.section), terms)
            if base > 0 and anchor is not None:
                w.anchored = anchor.problem(w.as_passage(0)) is None
                if w.anchored:
                    base += ANCHOR_BONUS
            w.score = base
            windows.append(w)
    windows.sort(key=lambda w: (-w.score, w.order))
    chosen: list[Window] = []
    used = 0
    for w in windows:
        if w.score <= 0 or len(chosen) >= max_passages:
            break
        size = len(w.text) + sum(len(h) for h in w.section)
        if used + size > max_chars and chosen:
            continue
        chosen.append(w)
        used += size
    return [w.as_passage(i) for i, w in enumerate(chosen, 1)]
