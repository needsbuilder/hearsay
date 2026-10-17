"""Documentation claims: official docs domain -> Tavily Search + Extract -> passages -> jury."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from .anchoring import Anchor
from .doc_urls import only_old_versions_note, order_and_dedupe
from .docs_domain import DocsTarget, resolve_docs
from .jury import run_jury
from .models import Claim, ClaimResult, ClaimType, DecisionPath, Verdict
from .passages import select_passages
from .tavily import TavilyBudgetExceeded, TavilyUnavailable

if TYPE_CHECKING:
    from .pipeline import Context

TOP_PAGES = 3


def docs_query(claim: Claim) -> str:
    sym = (claim.symbol or claim.package or "").strip("`")
    if claim.type == ClaimType.PARAMETER_EXISTS and sym and claim.parameter:
        return f"{sym} {claim.parameter.strip('`')} parameter"
    if claim.type == ClaimType.DEPRECATED and sym:
        since = f" {claim.since_version}" if claim.since_version else ""
        return f"{sym} deprecated{since}"
    return claim.statement[:350]


_LANG_SEGMENT = re.compile(
    r"/(?:projects/)?(de|es|fr|it|ja|ko|pl|pt|pt-br|ru|tr|uk|id|zh|zh-cn|zh-tw|zh_cn|zh_tw)(?:/|$)", re.I
)


def _prefer_english(hits: list) -> list:
    """Drop translated pages (/de/, /es/3.13/, ...) when untranslated ones exist."""
    english = [h for h in hits if not _LANG_SEGMENT.search(urlparse(h.url).path)]
    return english or hits


def _on_domain(url: str, domains: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def _unverifiable(claim: Claim, reason: str, **kw) -> ClaimResult:
    return ClaimResult(claim=claim, verdict=Verdict.UNVERIFIABLE, path=DecisionPath.NONE, reason=reason, **kw)


def fetch_pages(ctx: "Context", claim: Claim, target: DocsTarget, notes: list[str]) -> list[tuple[str, str, str]]:
    """(url, title, markdown) for the official pages about a claim: Tavily Search scoped
    to the docs domain, then Tavily Extract of the top results as whole pages."""
    assert ctx.tavily is not None
    query = docs_query(claim)
    pages: list[tuple[str, str, str]] = []
    if target.domains:
        hits = [h for h in ctx.tavily.search(query, target.domains) if _on_domain(h.url, target.domains)]
        if not hits:
            return []
        claimed_version = claim.version or claim.since_version
        top = order_and_dedupe(_prefer_english(hits), claimed_version)[:TOP_PAGES]
        note = only_old_versions_note([h.url for h in top], claimed_version)
        if note:
            notes.append(note)
        extracted, failed = ctx.tavily.extract([h.url for h in top])  # whole pages, headings kept
        texts = {p.url.rstrip("/"): p.text for p in extracted}
        for h in top:
            text = texts.get(h.url.rstrip("/"))
            if text:
                pages.append((h.url, h.title, text))
            elif h.content:
                pages.append((h.url, h.title, f"# {h.title}\n\n{h.content}" if h.title else h.content))
                notes.append(f"Extract failed for {h.url}; used the search snippet.")
    else:
        extracted, failed = ctx.tavily.extract(target.urls)
        pages = [(p.url, "", p.text) for p in extracted if p.text]
        if failed:
            notes.append(f"Extract failed for {', '.join(failed)}.")
    return pages


def check_docs_claim(ctx: "Context", claim: Claim) -> ClaimResult:
    target = resolve_docs(ctx.http, claim)
    if not target.found:
        return _unverifiable(claim, f"No official documentation source found: {target.how}.")
    notes = [f"Documentation source: {target.how}."]
    domains = target.domains or sorted({(urlparse(u).hostname or "") for u in target.urls})
    if ctx.tavily is None:
        return _unverifiable(claim, "Tavily is not configured (TAVILY_API_KEY).", docs_domains=domains, notes=notes)
    if ctx.llm is None:
        return _unverifiable(claim, "Documentation claims need the jury; model calls are off.", docs_domains=domains, notes=notes)

    try:
        pages = fetch_pages(ctx, claim, target, notes)
    except (TavilyBudgetExceeded, TavilyUnavailable) as exc:
        return _unverifiable(claim, str(exc), docs_domains=domains, notes=notes)
    query = docs_query(claim)
    if not pages:
        return _unverifiable(
            claim, f"Tavily found no pages on {', '.join(domains)} for {query!r}.",
            docs_domains=domains, notes=notes,
        )

    anchor = Anchor.for_claim(claim)
    if anchor is not None:
        notes.append(f"Anchoring: a quote counts only from a passage about {anchor.name}.")
    passages = select_passages(pages, claim, anchor=anchor)
    if not passages:
        return _unverifiable(
            claim, f"The documentation pages found do not mention the claim's terms ({query!r}).",
            docs_domains=domains, notes=notes,
        )

    s = ctx.settings
    assert s.adjudicator_model
    outcome = run_jury(ctx.llm, s.judge_models, s.adjudicator_model, claim, passages, anchor)
    return ClaimResult(
        claim=claim,
        verdict=outcome.verdict,
        path=outcome.path,
        source_url=outcome.url,
        quote=outcome.quote,
        reason=outcome.reason,
        judges=outcome.votes,
        adjudicator=outcome.adjudicator,
        docs_domains=domains,
        evidence=passages,
        notes=notes + outcome.notes,
    )
