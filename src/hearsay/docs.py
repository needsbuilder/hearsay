"""Documentation claims: official docs domain -> Tavily Search + Extract -> passages -> jury."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

from .docs_domain import resolve_docs
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


def _on_domain(url: str, domains: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d or host.endswith("." + d) for d in domains)


def _unverifiable(claim: Claim, reason: str, **kw) -> ClaimResult:
    return ClaimResult(claim=claim, verdict=Verdict.UNVERIFIABLE, path=DecisionPath.NONE, reason=reason, **kw)


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

    query = docs_query(claim)
    pages: list[tuple[str, str, str]] = []
    try:
        if target.domains:
            hits = [h for h in ctx.tavily.search(query, target.domains) if _on_domain(h.url, target.domains)]
            if not hits:
                return _unverifiable(
                    claim, f"Tavily found no pages on {', '.join(target.domains)} for {query!r}.",
                    docs_domains=domains, notes=notes,
                )
            top = hits[:TOP_PAGES]
            extracted, failed = ctx.tavily.extract([h.url for h in top], query)
            texts = {p.url.rstrip("/"): p.text for p in extracted}
            for h in top:
                text = texts.get(h.url.rstrip("/"))
                if text:
                    pages.append((h.url, h.title, text))
                elif h.content:
                    pages.append((h.url, h.title, h.content))
                    notes.append(f"Extract failed for {h.url}; used the search snippet.")
        else:
            extracted, failed = ctx.tavily.extract(target.urls, query)
            pages = [(p.url, "", p.text) for p in extracted if p.text]
            if failed:
                notes.append(f"Extract failed for {', '.join(failed)}.")
    except (TavilyBudgetExceeded, TavilyUnavailable) as exc:
        return _unverifiable(claim, str(exc), docs_domains=domains, notes=notes)

    passages = select_passages(pages, claim)
    if not passages:
        return _unverifiable(
            claim, f"The documentation pages found do not mention the claim's terms ({query!r}).",
            docs_domains=domains, notes=notes,
        )

    s = ctx.settings
    assert s.adjudicator_model
    outcome = run_jury(ctx.llm, s.judge_models, s.adjudicator_model, claim, passages)
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
