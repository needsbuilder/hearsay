"""Quote verification: a judge's quote must appear in the evidence it was shown."""

from __future__ import annotations

import re
import unicodedata

from .models import Passage

MIN_QUOTE_CHARS = 15

_QUOTES = str.maketrans(
    {
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'", "\u2032": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"', "\u2033": '"',
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-",
        "\u00a0": " ", "\u2009": " ", "\u202f": " ",
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
    s = s.replace("\u00b6", " ")
    s = _SPACE.sub(" ", s)
    return s.strip()


# The quote rule treats single and double quote marks as the same character
# (normalize() already folds the curly forms into straight ones). Judges
# often swap one for the other; nothing else is loosened.
_SAME_QUOTE_MARK = str.maketrans({'"': "'"})


def _trim(quote: str) -> str:
    q = normalize(quote)
    q = q.strip(" \"'")
    q = q.rstrip(" .,;:")
    return q


def quote_problem(quote: str | None, text: str) -> str | None:
    """None if the quote is a verbatim (normalised) substring of text, else the reason."""
    if not quote or not quote.strip():
        return "no quote given"
    q = _trim(quote).translate(_SAME_QUOTE_MARK)
    if len(q) < MIN_QUOTE_CHARS:
        return f"quote is shorter than {MIN_QUOTE_CHARS} characters"
    if q not in normalize(text).translate(_SAME_QUOTE_MARK):
        if "..." in q or "\u2026" in q:
            return "quote skips text with an ellipsis; it must be one contiguous span"
        return "quote does not appear in the evidence"
    return None


def find_quote_all(
    quote: str | None, passages: list[Passage], preferred: int | None = None
) -> tuple[list[Passage], str | None]:
    """Every passage that contains the quote (the one the judge named first), or the problem."""
    ordered = sorted(passages, key=lambda p: 0 if p.id == preferred else 1)
    found: list[Passage] = []
    last_problem = "no evidence passages"
    for p in ordered:
        problem = quote_problem(quote, p.text)
        if problem is None:
            found.append(p)
            continue
        last_problem = problem
        if problem == "no quote given" or problem.startswith("quote is shorter"):
            return [], problem
    return found, (None if found else last_problem)


def find_quote(quote: str | None, passages: list[Passage], preferred: int | None = None) -> tuple[Passage | None, str | None]:
    """Locate the passage that contains the quote; prefer the one the judge named."""
    found, problem = find_quote_all(quote, passages, preferred)
    return (found[0] if found else None), problem


def display_quote(quote: str | None) -> str | None:
    """The quote as a reader sees it on the page: link targets dropped, whitespace collapsed."""
    if quote is None:
        return None
    return _SPACE.sub(" ", _MD_LINK.sub(r"\1", quote)).strip()
