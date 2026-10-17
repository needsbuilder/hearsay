"""Guard rails for the public demo: per-address rate limit, a global daily cap on
new Tavily calls, a cap on concurrent live checks, and a request body limit.

All state is in memory. It resets when the process restarts.
"""

from __future__ import annotations

import json
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Callable

from ..tavily import TavilyBudgetExceeded, TavilyClient


class RateLimiter:
    """At most `limit` events per `window` seconds for each key (sliding window)."""

    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window
        self.clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> float | None:
        """Record an event for `key`. None if allowed, else seconds until the next one is."""
        now = self.clock()
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= now - self.window:
                events.popleft()
            if len(events) >= self.limit:
                return max(1.0, events[0] + self.window - now)
            events.append(now)
            if len(self._events) > 10_000:
                self._prune(now)
            return None

    def _prune(self, now: float) -> None:
        for key in [k for k, ev in self._events.items() if not ev or ev[-1] <= now - self.window]:
            del self._events[key]


def utc_day(clock: Callable[[], float] = time.time) -> str:
    return datetime.fromtimestamp(clock(), tz=timezone.utc).strftime("%Y-%m-%d")


class DailyCap:
    """A global budget of events per UTC day, shared by every request."""

    def __init__(self, limit: int, clock: Callable[[], float] = time.time):
        self.limit = limit
        self.clock = clock
        self._day = utc_day(clock)
        self._used = 0
        self._lock = threading.Lock()

    def _roll(self) -> None:
        today = utc_day(self.clock)
        if today != self._day:
            self._day, self._used = today, 0

    def take(self) -> bool:
        """Count one event if the budget allows it."""
        with self._lock:
            self._roll()
            if self._used >= self.limit:
                return False
            self._used += 1
            return True

    @property
    def used(self) -> int:
        with self._lock:
            self._roll()
            return self._used

    @property
    def remaining(self) -> int:
        return max(0, self.limit - self.used)


class Gate:
    """At most `limit` live checks at once; never waits."""

    def __init__(self, limit: int):
        self._sem = threading.BoundedSemaphore(max(1, limit))

    def try_enter(self) -> bool:
        return self._sem.acquire(blocking=False)

    def leave(self) -> None:
        self._sem.release()


class DemoTavily(TavilyClient):
    """TavilyClient that also draws every new (uncached) call from the demo's daily cap.

    Cached answers never reach `_guard`, so they cost nothing and are not
    limited. `capped` says which limit stopped a call: "request" or "daily".
    """

    def __init__(self, *args, daily: DailyCap, **kwargs):
        super().__init__(*args, **kwargs)
        self.daily = daily
        self.capped: str | None = None

    def _guard(self, endpoint: str, body: dict) -> None:
        if self.api_key and self.calls_made >= self.max_calls:
            self.capped = "request"
        elif self.api_key and not self.daily.take():
            self.capped = "daily"
            raise TavilyBudgetExceeded(
                f"The demo's daily limit of {self.daily.limit} new documentation lookups (Tavily calls) is used up; "
                "answers already in the cache still work"
            )
        super()._guard(endpoint, body)


class BodySizeLimit:
    """ASGI middleware: 413 when a request declares a body larger than `max_bytes`,
    411 when a request with a body gives no Content-Length.

    The server reads exactly Content-Length bytes, so the declared size is the
    size that reaches the app. Browsers and HTTP clients send it for forms and JSON.
    """

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope["method"] in ("POST", "PUT", "PATCH"):
            headers = dict(scope.get("headers") or [])
            declared = headers.get(b"content-length")
            if declared is None or not declared.isdigit():
                await _reject(send, 411, "length_required", "Send the request with a Content-Length header.")
                return
            if int(declared) > self.max_bytes:
                await _reject(send, 413, "request_too_large", "The request body is too large.")
                return
        await self.app(scope, receive, send)


async def _reject(send, status: int, error: str, message: str) -> None:
    body = json.dumps({"error": error, "message": message}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
        }
    )
    await send({"type": "http.response.body", "body": body})
