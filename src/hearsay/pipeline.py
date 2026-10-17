"""Wiring: extraction -> routing -> deterministic checks or docs + jury -> report."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Callable

import httpx

from ._version import __version__
from .cache import Cache
from .config import Settings
from .deterministic import (
    apply_negation,
    check_license,
    check_npm_deprecated,
    check_package_exists,
    check_version_exists,
    check_vulnerability,
)
from .docs import check_docs_claim
from .extract import extract_claims
from .http import Http, HttpError
from .llm import ChatModel, OpenAICompatibleClient
from .models import (
    Claim,
    ClaimResult,
    ClaimType,
    DecisionPath,
    ExtractionInfo,
    ModelConfig,
    Report,
    Usage,
    Verdict,
)
from .patterns import extract_with_patterns, pinned_claims
from .tavily import TavilyClient
from .versions import VersionError, normalize_ecosystem


class ConfigError(RuntimeError):
    pass


@dataclass
class Context:
    settings: Settings
    usage: Usage
    cache: Cache
    http: Http
    tavily: TavilyClient | None
    llm: ChatModel | None
    progress: Callable[[str], None] | None = None

    @classmethod
    def create(
        cls,
        settings: Settings | None = None,
        *,
        use_llm: bool = True,
        llm: ChatModel | None = None,
        transport: httpx.BaseTransport | None = None,
        progress: Callable[[str], None] | None = None,
    ) -> "Context":
        settings = settings or Settings.from_env()
        usage = Usage()
        cache = Cache(settings.cache_dir, refresh=settings.refresh_cache)
        http = Http(cache, usage, transport=transport, timeout=settings.http_timeout)
        tavily = None
        if settings.tavily_api_key:
            ledger = settings.cache_dir / "tavily-ledger.jsonl" if settings.cache_dir else None
            tavily = TavilyClient(http, settings.tavily_api_key, max_calls=settings.tavily_max_calls, ledger=ledger)
        model: ChatModel | None = None
        if use_llm:
            if llm is not None:
                model = llm
            else:
                problems = settings.llm_problems()
                if problems:
                    raise ConfigError(
                        "model settings missing: " + "; ".join(problems) + ". Set them (see .env.example) or use --no-llm."
                    )
                model = OpenAICompatibleClient(
                    settings.llm_base_url,
                    settings.llm_api_key,
                    cache,
                    usage,
                    timeout=settings.llm_timeout,
                    max_tokens=settings.llm_max_tokens,
                )
        return cls(settings, usage, cache, http, tavily, model, progress)

    def say(self, message: str) -> None:
        if self.progress:
            self.progress(message)

    def close(self) -> None:
        """Close the HTTP connections (long-running callers: the web app, the MCP server)."""
        self.http.close()
        client = getattr(self.llm, "client", None)
        if isinstance(client, httpx.Client):
            client.close()


DOCS_TYPES = {ClaimType.PARAMETER_EXISTS, ClaimType.API_BEHAVIOR, ClaimType.OTHER_EXTERNAL}


def check_claim(ctx: Context, claim: Claim) -> ClaimResult:
    """Route one claim to the source that can answer it."""
    try:
        if claim.type == ClaimType.PACKAGE_EXISTS:
            return apply_negation(check_package_exists(ctx.http, claim))
        if claim.type == ClaimType.VERSION_EXISTS:
            return apply_negation(check_version_exists(ctx.http, claim))
        if claim.type in (ClaimType.FIXES_VULNERABILITY, ClaimType.AFFECTED_BY_VULNERABILITY):
            return apply_negation(check_vulnerability(ctx.http, claim))
        if claim.type == ClaimType.LICENSE_IS:
            return apply_negation(check_license(ctx.http, claim))
        if claim.type == ClaimType.DEPRECATED:
            package_level = claim.package and (not claim.symbol or claim.symbol.strip("`") == claim.package)
            if package_level and normalize_ecosystem(claim.ecosystem) == "npm":
                result = check_npm_deprecated(ctx.http, claim)
                if result is not None:
                    return apply_negation(result)
            return check_docs_claim(ctx, claim)
        if claim.type in DOCS_TYPES:
            return check_docs_claim(ctx, claim)
    except (HttpError, VersionError) as exc:
        return ClaimResult(
            claim=claim, verdict=Verdict.UNVERIFIABLE, path=DecisionPath.NONE, reason=f"Lookup failed: {exc}"
        )
    return ClaimResult(claim=claim, verdict=Verdict.UNVERIFIABLE, path=DecisionPath.NONE, reason="Unsupported claim type.")


def _model_config(ctx: Context) -> ModelConfig:
    if ctx.llm is None:
        return ModelConfig()
    s = ctx.settings
    return ModelConfig(
        llm_base_url=s.llm_base_url,
        extract_model=s.extract_model,
        judge_models=list(s.judge_models),
        adjudicator_model=s.adjudicator_model,
    )


def check_claims(
    claims: list[Claim],
    *,
    context: Context | None = None,
    extraction: ExtractionInfo | None = None,
    settings: Settings | None = None,
    use_llm: bool = True,
) -> Report:
    ctx = context or Context.create(settings, use_llm=use_llm)
    results = []
    for i, claim in enumerate(claims, 1):
        if not claim.id:
            claim.id = f"c{i}"
        ctx.say(f"[{i}/{len(claims)}] {claim.type.value}: {claim.statement}")
        results.append(check_claim(ctx, claim))
    return Report(
        hearsay_version=__version__,
        totals=Report.count(results),
        results=results,
        extraction=extraction or ExtractionInfo(method="given", sentences=0),
        models=_model_config(ctx),
        usage=ctx.usage,
    )


def check(
    text: str,
    *,
    settings: Settings | None = None,
    use_llm: bool = True,
    context: Context | None = None,
) -> Report:
    """Extract the claims in `text` and check each one. The main library entry point."""
    ctx = context or Context.create(settings, use_llm=use_llm)
    if ctx.llm is not None:
        assert ctx.settings.extract_model
        ctx.say(f"extracting claims with {ctx.settings.extract_model}")
        claims, info = extract_claims(ctx.llm, ctx.settings.extract_model, text)
        claims = add_missed_pins(claims, text)
    else:
        claims, info = extract_with_patterns(text)
        claims = order_by_position(claims, text)
    ctx.say(f"{len(claims)} claims")
    return check_claims(claims, context=ctx, extraction=info)


def _pkg_key(name: str | None) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def add_missed_pins(claims: list[Claim], text: str) -> list[Claim]:
    """Add install-command and pin claims (pkg==1.2.3) the model did not extract."""
    covered = {(_pkg_key(c.package), (c.version or "").lower()) for c in claims if c.package}
    covered_pkgs = {p for p, _ in covered}
    out = list(claims)
    for pin in pinned_claims(text):
        key = (_pkg_key(pin.package), (pin.version or "").lower())
        if key in covered or (not pin.version and key[0] in covered_pkgs):
            continue
        covered.add(key)
        out.append(pin)
    return order_by_position(out, text)


def order_by_position(claims: list[Claim], text: str) -> list[Claim]:
    """Sort claims by where their source sentence appears in the input and renumber them."""
    def position(c: Claim) -> int:
        pos = text.find(c.source_sentence)
        return pos if pos >= 0 else len(text)

    ordered = sorted(claims, key=position)
    for i, c in enumerate(ordered, 1):
        c.id = f"c{i}"
    return ordered


def stderr_progress(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


__all__ = ["Context", "ConfigError", "check", "check_claims", "check_claim"]
