"""Turn a Report into what the page shows: badges, decision paths, the quote in
its passage, and each judge's vote with the reason it was kept or discarded."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

from markupsafe import Markup, escape

from ..models import ClaimResult, DecisionPath, JudgeVote, Passage, Report, Verdict
from ..quotes import normalize

VERDICT_LABEL = {
    Verdict.SUPPORTED: "Supported",
    Verdict.CONTRADICTED: "Contradicted",
    Verdict.UNVERIFIABLE: "Unverifiable",
}

PATH_LABEL = {
    DecisionPath.REGISTRY: "Registry",
    DecisionPath.ADVISORY: "Advisory",
    DecisionPath.JURY: "Jury",
    DecisionPath.ADJUDICATOR: "Adjudicator",
    DecisionPath.NONE: "Not decided",
}

PATH_HELP = {
    DecisionPath.REGISTRY: "PyPI, npm or deps.dev metadata decided it, no model.",
    DecisionPath.ADVISORY: "OSV advisory data decided it, no model.",
    DecisionPath.JURY: "Official documentation; the judges agreed after the quote and anchoring rules.",
    DecisionPath.ADJUDICATOR: "Official documentation; the judges disagreed and the adjudicator decided.",
    DecisionPath.NONE: "Nothing decided it: no official source, an unsupported ecosystem, a limit, a lookup error, or model calls off.",
}

CONTEXT_CHARS = 260


@dataclass
class QuoteView:
    before: str
    quote: str
    after: str
    section: str = ""
    url: str | None = None
    in_context: bool = False  # True when the quote was located inside an evidence passage


@dataclass
class VoteView:
    who: str
    model: str
    stated: str  # what the model answered
    effective: Verdict  # what counted after the rules
    quote: str | None
    quote_found: bool
    anchored: bool | None
    discarded: str | None  # why the vote did not count as stated
    reasoning: str
    url: str | None


@dataclass
class ClaimView:
    result: ClaimResult
    verdict_label: str
    path_label: str
    path_help: str
    quote: QuoteView | None
    field_quote: bool  # registry/advisory: the quote is a field and value, not prose
    votes: list[VoteView] = field(default_factory=list)


def safe_url(url: str | None) -> str | None:
    """Only http(s) URLs become links."""
    if not url:
        return None
    scheme = urlparse(url).scheme.lower()
    return url if scheme in ("http", "https") else None


_TICKS = re.compile(r"`([^`\n]+)`")


def code_spans(text: str | None) -> Markup:
    """Escape the text, then show `backtick spans` as <code>. Nothing else is interpreted."""
    escaped = str(escape(text or ""))
    return Markup(_TICKS.sub(r"<code>\1</code>", escaped))


def _trim(q: str) -> str:
    return normalize(q).strip(" \"'").rstrip(" .,;:")


def _cut_before(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[-limit:]
    space = cut.find(" ")
    return "..." + (cut[space + 1 :] if 0 <= space < 40 else cut)


def _cut_after(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    return (cut[:space] if space > limit - 40 else cut) + "..."


def locate_quote(quote: str, passages: list[Passage], url: str | None) -> QuoteView | None:
    """Find the quote in the passage it came from and return it with its surroundings.

    The jury's quote rule compares normalised text (Markdown, quotes, dashes and
    whitespace ignored), so the passage is shown in that same normalised form.
    """
    wanted = _trim(quote)
    if not wanted:
        return None
    ordered = sorted(passages, key=lambda p: 0 if url and p.url.rstrip("/") == url.rstrip("/") else 1)
    for p in ordered:
        text = normalize(p.text)
        i = text.find(wanted)
        if i < 0:
            continue
        return QuoteView(
            before=_cut_before(text[:i], CONTEXT_CHARS),
            quote=text[i : i + len(wanted)],
            after=_cut_after(text[i + len(wanted) :], CONTEXT_CHARS),
            section=" > ".join(p.section),
            url=p.url,
            in_context=True,
        )
    return None


def _vote_view(v: JudgeVote, n: int) -> VoteView:
    who = "Adjudicator" if v.role == "adjudicator" else f"Judge {n}"
    stated = v.stated_verdict.value if v.stated_verdict else "invalid output"
    discarded = None
    if v.error:
        discarded = v.error
    elif v.stated_verdict is not None and v.stated_verdict != v.verdict:
        discarded = "the stated verdict did not count"
    return VoteView(
        who=who,
        model=v.model,
        stated=stated,
        effective=v.verdict,
        quote=v.quote,
        quote_found=v.quote_found,
        anchored=v.anchored,
        discarded=discarded,
        reasoning=v.reasoning,
        url=safe_url(v.url),
    )


def claim_view(r: ClaimResult) -> ClaimView:
    field_quote = r.path in (DecisionPath.REGISTRY, DecisionPath.ADVISORY)
    quote = None
    if r.quote:
        if not field_quote:
            quote = locate_quote(r.quote, r.evidence, r.source_url)
        if quote is None:
            quote = QuoteView(before="", quote=r.quote, after="", url=r.source_url)
    votes = [_vote_view(v, i) for i, v in enumerate(r.judges, 1)]
    if r.adjudicator is not None:
        votes.append(_vote_view(r.adjudicator, len(votes) + 1))
    return ClaimView(
        result=r,
        verdict_label=VERDICT_LABEL[r.verdict],
        path_label=PATH_LABEL[r.path],
        path_help=PATH_HELP[r.path],
        quote=quote,
        field_quote=field_quote,
        votes=votes,
    )


def report_view(report: Report) -> list[ClaimView]:
    return [claim_view(r) for r in report.results]
