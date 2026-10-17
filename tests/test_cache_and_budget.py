import json

import httpx
import pytest

from hearsay.cache import Cache
from hearsay.http import Http, HttpError
from hearsay.llm import OpenAICompatibleClient
from hearsay.models import Usage
from hearsay.tavily import TavilyBudgetExceeded, TavilyClient, TavilyUnavailable


class Counting:
    def __init__(self, handler):
        self.handler = handler
        self.requests: list[httpx.Request] = []

    def transport(self):
        def h(request):
            self.requests.append(request)
            return self.handler(request)

        return httpx.MockTransport(h)


def json_response(payload, status=200):
    return lambda request: httpx.Response(status, json=payload)


def test_http_second_call_is_a_cache_hit(tmp_path):
    counter = Counting(json_response({"ok": True}))
    usage = Usage()
    http = Http(Cache(tmp_path), usage, transport=counter.transport(), retry_delay=0)
    a = http.get("https://example.org/a")
    b = http.get("https://example.org/a")
    assert a.data == b.data == {"ok": True}
    assert not a.from_cache and b.from_cache
    assert len(counter.requests) == 1
    assert usage.http_requests == 1 and usage.http_cache_hits == 1


def test_cache_survives_a_new_client(tmp_path):
    counter = Counting(json_response({"n": 1}))
    Http(Cache(tmp_path), Usage(), transport=counter.transport()).get("https://example.org/a")
    again = Http(Cache(tmp_path), Usage(), transport=counter.transport()).get("https://example.org/a")
    assert again.from_cache and len(counter.requests) == 1


def test_different_request_is_a_miss(tmp_path):
    counter = Counting(json_response({"ok": True}))
    http = Http(Cache(tmp_path), Usage(), transport=counter.transport())
    http.post("https://example.org/q", {"q": 1})
    http.post("https://example.org/q", {"q": 2})
    http.get("https://example.org/q", headers={"Accept": "x"})
    assert len(counter.requests) == 3


def test_not_found_is_cached_but_server_errors_are_not(tmp_path):
    counter = Counting(lambda r: httpx.Response(404 if r.url.path == "/missing" else 503, text="no"))
    http = Http(Cache(tmp_path), Usage(), transport=counter.transport(), retry_delay=0)
    assert http.get("https://example.org/missing").status == 404
    assert http.get("https://example.org/missing").from_cache
    with pytest.raises(HttpError):
        http.get("https://example.org/broken")
    with pytest.raises(HttpError):
        http.get("https://example.org/broken")
    assert sum(1 for r in counter.requests if r.url.path == "/broken") == 6  # 3 attempts each, never cached


def test_secrets_are_not_stored_or_part_of_the_key(tmp_path):
    counter = Counting(json_response({"results": []}))
    http = Http(Cache(tmp_path), Usage(), transport=counter.transport())
    http.post("https://api.tavily.com/search", {"query": "q"}, secret_headers={"Authorization": "Bearer SECRET-1"})
    hit = http.post("https://api.tavily.com/search", {"query": "q"}, secret_headers={"Authorization": "Bearer SECRET-2"})
    assert hit.from_cache
    assert counter.requests[0].headers["Authorization"] == "Bearer SECRET-1"
    stored = "".join(p.read_text() for p in tmp_path.rglob("*.json"))
    assert "SECRET" not in stored


def test_refresh_skips_reads_but_writes(tmp_path):
    counter = Counting(json_response({"v": 1}))
    Http(Cache(tmp_path), Usage(), transport=counter.transport()).get("https://example.org/a")
    Http(Cache(tmp_path, refresh=True), Usage(), transport=counter.transport()).get("https://example.org/a")
    assert len(counter.requests) == 2


def test_llm_calls_are_cached(tmp_path):
    reply = {"choices": [{"message": {"content": '{"ok": true}'}}]}
    counter = Counting(json_response(reply))
    usage = Usage()
    client = OpenAICompatibleClient("http://llm.invalid/v1", "k", Cache(tmp_path), usage, transport=counter.transport())
    messages = [{"role": "user", "content": "hi"}]
    assert client.complete("m", messages) == '{"ok": true}'
    assert client.complete("m", messages) == '{"ok": true}'
    assert client.complete("other-model", messages) == '{"ok": true}'
    assert len(counter.requests) == 2
    assert usage.llm_calls == 2 and usage.llm_cache_hits == 1
    body = json.loads(counter.requests[0].content)
    assert body["temperature"] == 0 and body["response_format"] == {"type": "json_object"}


# ---------------------------------------------------------------- Tavily budget


def tavily(tmp_path, max_calls, key="test-key"):
    counter = Counting(json_response({"results": [{"url": "https://docs.example.org/a", "title": "A", "content": "c", "score": 0.9}]}))
    http = Http(Cache(tmp_path), Usage(), transport=counter.transport())
    ledger = tmp_path / "ledger.jsonl"
    return TavilyClient(http, key, max_calls=max_calls, ledger=ledger), counter, ledger


def test_budget_cap_refuses_extra_calls(tmp_path):
    client, counter, ledger = tavily(tmp_path, max_calls=2)
    client.search("one", ["docs.example.org"])
    client.search("two", ["docs.example.org"])
    with pytest.raises(TavilyBudgetExceeded):
        client.search("three", ["docs.example.org"])
    assert len(counter.requests) == 2
    assert len(ledger.read_text().splitlines()) == 2


def test_cached_calls_do_not_count_against_the_budget(tmp_path):
    client, counter, _ = tavily(tmp_path, max_calls=1)
    client.search("one", ["docs.example.org"])
    for _ in range(5):
        client.search("one", ["docs.example.org"])
    assert client.calls_made == 1 and len(counter.requests) == 1


def test_search_request_is_scoped_to_domains(tmp_path):
    client, counter, _ = tavily(tmp_path, max_calls=5)
    hits = client.search("requests.get timeout parameter", ["requests.readthedocs.io"])
    body = json.loads(counter.requests[0].content)
    assert body["include_domains"] == ["requests.readthedocs.io"]
    assert counter.requests[0].headers["Authorization"] == "Bearer test-key"
    assert hits[0].url == "https://docs.example.org/a"


def test_missing_key_refuses_before_any_call(tmp_path):
    client, counter, _ = tavily(tmp_path, max_calls=5, key=None)
    with pytest.raises(TavilyUnavailable):
        client.search("x", ["docs.example.org"])
    assert counter.requests == []
