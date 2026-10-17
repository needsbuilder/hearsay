"""Duplicate pages and old versions of documentation among search results."""

import json

import httpx

from hearsay.cache import Cache
from hearsay.config import Settings
from hearsay.doc_urls import doc_version, only_old_versions_note, order_and_dedupe, page_key
from hearsay.docs import fetch_pages
from hearsay.docs_domain import DocsTarget
from hearsay.http import Http
from hearsay.models import Usage
from hearsay.pipeline import Context
from hearsay.tavily import SearchHit, TavilyClient

from support import claim


def hit(url):
    return SearchHit(url=url, title="", content="", score=0.0)


def test_same_page_under_several_urls():
    same = [
        "https://docs.stripe.com/api/idempotent_requests?__=",
        "https://docs.stripe.com/api/idempotent_requests?api-version=2025-07-30.preview",
        "https://docs.stripe.com/api/idempotent_requests?lang=go",
        "https://docs.stripe.com/api/idempotent_requests/",
        "https://docs.stripe.com/api/idempotent_requests#example",
        "https://www.docs.stripe.com/api/idempotent_requests",
    ]
    assert len({page_key(u) for u in same}) == 1
    assert page_key("https://requests.readthedocs.io/en/latest/user/advanced") == page_key(
        "https://requests.readthedocs.io/en/master/user/advanced/"
    )
    assert page_key("https://nodejs.org/api/fs.html") == page_key("https://nodejs.org/api/fs")
    # different pages stay different
    assert page_key("https://nodejs.org/api/fs.html") != page_key("https://nodejs.org/api/fs.html?id=2")
    assert page_key("https://docs.python.org/3/library/json.html") != page_key("https://docs.python.org/2.7/library/json.html")


def test_versions_in_urls():
    assert doc_version("https://docs.python.org/2.7/library/json.html") == "2.7"
    assert doc_version("https://docs.python.org/3.4/library/json.html") == "3.4"
    assert doc_version("https://docs.python.org/3/library/json.html") is None
    assert doc_version("https://docs.python.org/ja/3.12/library/json.html") == "3.12"
    assert doc_version("https://nodejs.org/docs/latest-v18.x/api/globals.html") == "18"
    assert doc_version("https://nodejs.org/dist/v8.0.0/docs/api/fs.html") == "8.0.0"
    assert doc_version("https://nodejs.org/api/globals.html") is None
    assert doc_version("https://docs.stripe.com/api/v1/refunds") is None  # an API version, not a docs version


def test_dedupe_frees_extract_slots():
    hits = [hit("https://x.dev/a"), hit("https://x.dev/a/"), hit("https://x.dev/a#b"), hit("https://x.dev/b"), hit("https://x.dev/c")]
    assert [h.url for h in order_and_dedupe(hits)][:3] == ["https://x.dev/a", "https://x.dev/b", "https://x.dev/c"]


JSON_DUMPS = [
    "https://docs.python.org/2.7/library/json.html",
    "https://docs.python.org/3.4/library/json.html",
    "https://docs.python.org/3.5/library/json.html",
    "https://docs.python.org/3/library/json.html",
]


def test_current_docs_first_then_newer_versions():
    ordered = [h.url for h in order_and_dedupe([hit(u) for u in JSON_DUMPS])]
    assert ordered == [JSON_DUMPS[3], JSON_DUMPS[2], JSON_DUMPS[1], JSON_DUMPS[0]]


def test_a_claimed_version_wins():
    ordered = [h.url for h in order_and_dedupe([hit(u) for u in JSON_DUMPS], claimed_version="3.4")]
    assert ordered[0] == JSON_DUMPS[1]


def test_note_when_only_old_versions_came_back():
    note = only_old_versions_note(JSON_DUMPS[:3])
    assert note.startswith("Only version-specific documentation pages came back (versions 3.5, 3.4, 2.7)")
    assert only_old_versions_note(JSON_DUMPS) is None
    assert only_old_versions_note(JSON_DUMPS[1:2], claimed_version="3.4") is None


def test_fetch_pages_uses_current_docs_and_reports_old_only(tmp_path):
    """The json.dumps sort_keys case: Tavily returned Python 2.7, 3.4 and 3.5 pages."""
    extract_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path == "/search":
            urls = JSON_DUMPS[:3] if "only old" in body["query"] else JSON_DUMPS
            return httpx.Response(200, json={"results": [{"url": u, "title": "json", "content": "c", "score": 1} for u in urls]})
        extract_requests.append(body["urls"])
        return httpx.Response(200, json={"results": [{"url": u, "raw_content": "# json\n\nsort_keys is a parameter."} for u in body["urls"]]})

    usage = Usage()
    http = Http(Cache(tmp_path), usage, transport=httpx.MockTransport(handler))
    ctx = Context(Settings(cache_dir=None), usage, Cache(None), http, TavilyClient(http, "k", max_calls=10), None)
    target = DocsTarget(domains=["docs.python.org"], how="test")

    notes: list[str] = []
    c = claim("parameter_exists", "json.dumps accepts sort_keys.", symbol="json.dumps", parameter="sort_keys")
    pages = fetch_pages(ctx, c, target, notes)
    assert [p[0] for p in pages] == [JSON_DUMPS[3], JSON_DUMPS[2], JSON_DUMPS[1]]
    assert not any(n.startswith("Only version-specific") for n in notes)

    notes = []
    old = claim("api_behavior", "only old json.dumps sort_keys", symbol="json.dumps", subject="Python")
    fetch_pages(ctx, old, target, notes)
    assert any(n.startswith("Only version-specific documentation pages came back") for n in notes)
