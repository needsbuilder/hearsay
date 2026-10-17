"""Quote verification: a judge's quote must appear in the evidence it was shown."""

from __future__ import annotations

import re
import unicodedata

from .models import Passage

MIN_QUOTE_CHARS = 15

_QUOTES = str.maketrans(
    {
        "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
        "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
        "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
        " ": " ", " ": " ", " ": " ",
    }
)
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_MARKS = re.compile(r"[`*]|(?<!\w)_{1,2}|_{1,2}(?!\w)|\\(?=[\\`*_{}\[\]()#+\-.!|])")
_HEADING = re.compile(r"(^|\n)\s*#{1,6}\s+")
_SPACE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Unicode, quote and dash forms, Markdown markup and whitespace are ignored."""
    s = unicodedata.normalize("NFKC", text or "")
    s = s.translate(_QUOTES)
    s = _MD_LINK.sub(r"\1", s)
    s = _HEADING.sub(r"\1", s)
    s = _MD_MARKS.sub("", s)
    s = s.replace("¶", " ")
    s = _SPACE.sub(" ", s)
    return s.strip()


def _trim(quote: str) -> str:
    q = normalize(quote)
    q = q.strip(" \"'")
    q = q.rstrip(" .,;:")
    return q


def quote_problem(quote: str | None, text: str) -> str | None:
    """None if the quote is a verbatim (normalised) substring of text, else the reason."""
    if not quote or not quote.strip():
        return "no quote given"
    q = _trim(quote)
    if len(q) < MIN_QUOTE_CHARS:
        return f"quote is shorter than {MIN_QUOTE_CHARS} characters"
    if q not in normalize(text):
        if "..." in q or "…" in q:
            return "quote skips text with an ellipsis; it must be one contiguous span"
        return "quote does not appear in the evidence"
    return None


def find_quote(quote: str | None, passages: list[Passage], preferred: int | None = None) -> tuple[Passage | None, str | None]:
    """Locate the passage that contains the quote; prefer the one the judge named."""
    ordered = sorted(passages, key=lambda p: 0 if p.id == preferred else 1)
    last_problem = "no evidence passages"
    for p in ordered:
        problem = quote_problem(quote, p.text)
        if problem is None:
            return p, None
        last_problem = problem
        if problem == "no quote given" or problem.startswith("quote is shorter"):
            return None, problem
    return None, last_problem


def display_quote(quote: str | None) -> str | None:
    """The quote as a reader sees it on the page: link targets dropped, whitespace collapsed."""
    if quote is None:
        return None
    return _SPACE.sub(" ", _MD_LINK.sub(r"\1", quote)).strip()
