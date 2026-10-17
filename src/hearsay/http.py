"""Cached JSON-over-HTTP client used for registries, OSV, deps.dev, GitHub and Tavily."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from ._version import __version__
from .cache import Cache
from .models import Usage

USER_AGENT = f"hearsay/{__version__} (claim checker)"

# Answers worth remembering: "found" and "not found". Errors are retried next run.
CACHEABLE_STATUS = {200, 404, 410}
RETRY_STATUS = {429, 500, 502, 503, 504}


class HttpError(RuntimeError):
    pass


@dataclass
class HttpResult:
    url: str
    status: int
    data: Any
    from_cache: bool

    @property
    def ok(self) -> bool:
        return self.status == 200


class Http:
    def __init__(
        self,
        cache: Cache,
        usage: Usage,
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
        retry_delay: float = 1.5,
    ):
        self.cache = cache
        self.usage = usage
        self.retry_delay = retry_delay
        self.client = httpx.Client(
            transport=transport,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )

    def _count(self, namespace: str, cached: bool) -> None:
        if namespace == "tavily":
            if cached:
                self.usage.tavily_cache_hits += 1
            else:
                self.usage.tavily_calls += 1
        else:
            if cached:
                self.usage.http_cache_hits += 1
            else:
                self.usage.http_requests += 1

    def request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        headers: dict[str, str] | None = None,
        secret_headers: dict[str, str] | None = None,
        namespace: str = "http",
        before_network: Callable[[], None] | None = None,
    ) -> HttpResult:
        """Send a request, or answer it from the cache.

        `headers` are part of the cache key; `secret_headers` (API keys) are not
        and are never stored. `before_network` runs only on a cache miss, right
        before the real call; it may raise to stop the call (budget checks).
        """
        key = {
            "method": method.upper(),
            "url": url,
            "params": params or None,
            "json": json_body,
            "headers": headers or None,
        }
        cached = self.cache.get(namespace, key)
        if not Cache.is_missing(cached):
            self._count(namespace, cached=True)
            return HttpResult(url=url, status=cached["status"], data=cached["data"], from_cache=True)

        if before_network is not None:
            before_network()

        all_headers = {**(headers or {}), **(secret_headers or {})}
        response: httpx.Response | None = None
        for attempt in range(3):
            try:
                response = self.client.request(
                    method, url, params=params, json=json_body, headers=all_headers
                )
            except httpx.HTTPError as exc:
                if attempt == 2:
                    raise HttpError(f"{method} {url} failed: {exc.__class__.__name__}") from None
                time.sleep(self.retry_delay * (attempt + 1))
                continue
            if response.status_code in RETRY_STATUS and attempt < 2:
                time.sleep(self.retry_delay * (attempt + 1))
                continue
            break
        assert response is not None
        self._count(namespace, cached=False)

        try:
            data: Any = response.json()
        except ValueError:
            data = response.text
        if response.status_code not in CACHEABLE_STATUS:
            detail = data if isinstance(data, str) else str(data)
            raise HttpError(f"{method} {url} returned HTTP {response.status_code}: {detail[:200]}")
        self.cache.put(namespace, key, {"status": response.status_code, "data": data})
        return HttpResult(url=url, status=response.status_code, data=data, from_cache=False)

    def get(self, url: str, **kwargs: Any) -> HttpResult:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, json_body: Any, **kwargs: Any) -> HttpResult:
        return self.request("POST", url, json_body=json_body, **kwargs)

    def close(self) -> None:
        self.client.close()
