"""Test helpers: recorded fixtures, a transport that refuses the network, a fake model."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import httpx

from hearsay.cache import Cache
from hearsay.config import Settings
from hearsay.http import Http
from hearsay.models import Claim, ClaimType, Usage
from hearsay.pipeline import Context
from hearsay.tavily import TavilyClient

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_CACHE = FIXTURES / "cache"


class ReadOnlyCache(Cache):
    """The recorded fixtures: answers real responses, never writes."""

    def put(self, namespace, request, response) -> None:  # noqa: D401
        return None


def refuse_network() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"network call in tests: {request.method} {request.url}")

    return httpx.MockTransport(handler)


class FakeLLM:
    """Scripted model. `script` maps model name -> list of replies (used in order),
    or is a function (model, messages) -> reply."""

    def __init__(self, script: dict[str, list[str]] | Callable[[str, list[dict]], str]):
        self.script = script
        self.calls: list[tuple[str, list[dict]]] = []

    def complete(self, model: str, messages: list[dict], *, json_mode: bool = True) -> str:
        self.calls.append((model, messages))
        if callable(self.script):
            return self.script(model, messages)
        queue = self.script.get(model)
        if not queue:
            raise AssertionError(f"FakeLLM has no reply left for {model}")
        return queue.pop(0)


def judge_reply(verdict: str, quote: str = "", url: str | None = None, reasoning: str = "r") -> str:
    return json.dumps({"reasoning": reasoning, "verdict": verdict, "url": url, "quote": quote})


def fixture_context(
    *,
    llm: FakeLLM | None = None,
    judges: list[str] | None = None,
    adjudicator: str = "big-judge",
    tavily: bool = True,
) -> Context:
    settings = Settings(
        llm_base_url="http://fake-llm.invalid/v1",
        llm_api_key="unused",
        extract_model="fake-extractor",
        judge_models=judges or ["judge-a", "judge-b"],
        adjudicator_model=adjudicator,
        tavily_api_key="unused" if tavily else None,
        cache_dir=None,
    )
    usage = Usage()
    cache = ReadOnlyCache(FIXTURE_CACHE)
    http = Http(cache, usage, transport=refuse_network(), retry_delay=0)
    tav = TavilyClient(http, settings.tavily_api_key, max_calls=settings.tavily_max_calls) if tavily else None
    return Context(settings, usage, cache, http, tav, llm)


def claim(kind: str, statement: str = "a claim for tests", **fields) -> Claim:
    fields.setdefault("source_sentence", statement)
    return Claim(type=ClaimType(kind), statement=statement, **fields)


# Claims whose real responses are recorded in tests/fixtures/cache.
# Registry and advisory lookups are recorded live; Tavily responses are
# copied from the development cache (see tests/record_fixtures.py).
DOCS_CLAIMS = {
    "requests_timeout": dict(
        kind="parameter_exists",
        statement="requests.get accepts a timeout parameter.",
        symbol="requests.get",
        parameter="timeout",
        subject="Python",
    ),
    "github_matrix": dict(
        kind="other_external",
        statement="GitHub Actions allows at most 256 jobs per workflow run in a matrix.",
        subject="GitHub Actions",
    ),
    "utcnow": dict(
        kind="deprecated",
        statement="datetime.utcnow() is deprecated since Python 3.12.",
        symbol="datetime.utcnow()",
        since_version="3.12",
        subject="Python",
    ),
}


def docs_claim(name: str) -> Claim:
    spec = dict(DOCS_CLAIMS[name])
    kind = spec.pop("kind")
    statement = spec.pop("statement")
    return claim(kind, statement, **spec)
