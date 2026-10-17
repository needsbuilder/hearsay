"""Tavily Search and Extract, cached and capped per run.

Search is always scoped to official documentation domains (include_domains).
Extract is called on the top results with the claim as the reranking query,
so only the most relevant chunks of each page come back.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

from .http import Http

TAVILY = "https://api.tavily.com"


class TavilyBudgetExceeded(RuntimeError):
    pass


class TavilyUnavailable(RuntimeError):
    pass


@dataclass
class SearchHit:
    url: str
    title: str
    content: str
    score: float


@dataclass
class Page:
    url: str
    text: str


class TavilyClient:
    def __init__(
        self,
        http: Http,
        api_key: str | None,
        *,
        max_calls: int = 20,
        ledger: Path | None = None,
    ):
        self.http = http
        self.api_key = api_key
        self.max_calls = max_calls
        self.calls_made = 0  # real (uncached) calls in this run
        self.ledger = ledger

    def _guard(self, endpoint: str, body: dict) -> None:
        if not self.api_key:
            raise TavilyUnavailable("TAVILY_API_KEY is not set")
        if self.calls_made >= self.max_calls:
            raise TavilyBudgetExceeded(
                f"Tavily per-run budget of {self.max_calls} calls reached (HEARSAY_TAVILY_MAX_CALLS)"
            )
        self.calls_made += 1
        if self.ledger is not None:
            self.ledger.parent.mkdir(parents=True, exist_ok=True)
            summary = body.get("query") if endpoint == "search" else body.get("urls")
            with self.ledger.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "endpoint": endpoint, "request": summary}) + "\n")

    def _post(self, endpoint: str, body: dict) -> dict:
        res = self.http.post(
            f"{TAVILY}/{endpoint}",
            body,
            secret_headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else None,
            namespace="tavily",
            before_network=lambda: self._guard(endpoint, body),
        )
        if res.status != 200 or not isinstance(res.data, dict):
            raise TavilyUnavailable(f"Tavily {endpoint} returned HTTP {res.status}")
        return res.data

    def search(self, query: str, domains: list[str], *, max_results: int = 5) -> list[SearchHit]:
        body = {
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_domains": domains,
            "include_answer": False,
            "include_raw_content": False,
        }
        data = self._post("search", body)
        hits = [
            SearchHit(
                url=r.get("url", ""),
                title=r.get("title") or "",
                content=r.get("content") or "",
                score=float(r.get("score") or 0.0),
            )
            for r in data.get("results") or []
            if r.get("url")
        ]
        return hits

    def extract(
        self, urls: list[str], query: str | None = None, *, chunks_per_source: int = 5
    ) -> tuple[list[Page], list[str]]:
        """Page text as Markdown. Without `query` the whole page comes back, headings
        included, which Hearsay needs to tie each passage to its section. With
        `query`, Tavily returns only its top-ranked chunks, joined by [...]."""
        body: dict = {"urls": urls, "extract_depth": "basic", "format": "markdown"}
        if query is not None:
            body["query"] = query
            body["chunks_per_source"] = chunks_per_source
        data = self._post("extract", body)
        pages = [Page(url=r.get("url", ""), text=r.get("raw_content") or "") for r in data.get("results") or []]
        failed = [f.get("url", "") for f in data.get("failed_results") or []]
        return pages, failed
