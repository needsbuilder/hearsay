"""Web demo: pages, JSON API, bundled examples and the demo's limits. No network, no model calls."""

import json
import re
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from hearsay.config import Settings
from hearsay.web.app import WebConfig, create_app
from hearsay.web.demo import load_bundle
from hearsay.web.limits import BodySizeLimit, DailyCap, DemoTavily, RateLimiter
from hearsay.web.views import locate_quote, safe_url
from hearsay.models import Passage

from support import FakeLLM, refuse_network

EXAMPLES = Path(__file__).parent.parent / "examples"
BUNDLE = load_bundle()


def no_models(**overrides) -> Settings:
    """Server settings without model ids or keys: live checks use the pattern extractor."""
    return Settings(cache_dir=None, **overrides)


def make_client(config: WebConfig | None = None, *, settings=None, llm=None) -> TestClient:
    settings = settings or no_models()
    app = create_app(
        config or WebConfig(),
        bundle=BUNDLE,
        settings_factory=lambda: settings,
        transport=refuse_network(),
        llm=llm,
    )
    return TestClient(app)


# ---------------------------------------------------------------- bundled examples


@pytest.mark.parametrize("example_id", [e.id for e in BUNDLE.examples])
def test_bundled_example_replays_the_recorded_report_without_any_call(example_id):
    recorded = json.loads((EXAMPLES / f"{example_id}.report.json").read_text())
    report = BUNDLE.report(example_id)
    assert report.totals.model_dump() == recorded["totals"]
    assert [(r.claim.statement, r.verdict.value, r.path.value) for r in report.results] == [
        (r["claim"]["statement"], r["verdict"], r["path"]) for r in recorded["results"]
    ]
    u = report.usage
    assert (u.http_requests, u.tavily_calls, u.llm_calls) == (0, 0, 0)
    assert u.http_cache_hits + u.tavily_cache_hits + u.llm_cache_hits > 0


def test_example_page_shows_badges_paths_quotes_and_votes():
    page = make_client().get("/examples/agent-pr")
    assert page.status_code == 200
    html = page.text
    assert "Report: Agent pull request" in html
    assert "replayed from the recorded cache with no API calls" in html
    assert html.count('class="badge v-contradicted"') >= 5
    for label in ("Advisory", "Registry", "Jury", "Adjudicator"):
        assert f"Decided by: {label}" in html
    # The jury's quote is highlighted inside the passage it came from.
    assert "<mark>Deprecated since version 3.10, removed in version 3.12</mark>" in html
    # Votes, including one discarded by the quote rule, with the reason.
    assert "Why the vote did not count as answered" in html
    assert "quote does not appear in the evidence" in html
    assert "https://docs.python.org/3/library/distutils.html" in html


def test_example_page_for_unknown_id_is_404():
    assert make_client().get("/examples/nope").status_code == 404


def test_api_example_and_exact_text_are_served_from_the_bundle():
    client = make_client(WebConfig(rate_limit=0))  # live checks would be refused
    by_id = client.post("/api/check", json={"example": "chat-answer"})
    assert by_id.status_code == 200
    assert by_id.headers["x-hearsay-run"] == "example"
    assert by_id.json()["totals"]["supported"] == 5
    text = (EXAMPLES / "chat-answer.md").read_text().replace("\n", "\r\n")  # what a browser form sends
    by_text = client.post("/api/check", json={"text": text})
    assert by_text.status_code == 200 and by_text.headers["x-hearsay-example"] == "chat-answer"
    assert client.get("/api/examples/agent-pr").json()["totals"]["claims"] == 11
    assert [e["id"] for e in client.get("/api/examples").json()] == ["agent-pr", "chat-answer"]


def test_healthz():
    data = make_client().get("/healthz").json()
    assert data["status"] == "ok"
    assert data["examples"] == 2
    assert data["models_configured"] is False and data["tavily_configured"] is False
    assert data["tavily_daily_cap"] == WebConfig().tavily_daily_cap


# ---------------------------------------------------------------- live checks


def test_live_check_without_models_uses_patterns_and_says_so():
    # fastapi's PyPI answer is in the bundle's snapshot, which backs live checks too.
    res = make_client().post("/api/check", json={"text": "Run pip install fastapi==0.200.0 to get the new router."})
    assert res.status_code == 200
    assert res.headers["x-hearsay-run"] == "live"
    data = res.json()
    assert data["extraction"]["method"] == "patterns"
    assert [(r["claim"]["package"], r["verdict"]) for r in data["results"]] == [("fastapi", "contradicted")]
    assert "Model calls are not configured" in res.headers["x-hearsay-notice"]


def test_form_post_renders_the_report_and_escapes_the_input():
    text = "<script>alert(1)</script> Run pip install fastapi==0.200.0 now"
    page = make_client().post("/check", data={"text": text})
    assert page.status_code == 200
    assert "<script>alert(1)</script>" not in page.text
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page.text
    assert "fastapi 0.200.0 is published on PyPI." in page.text
    assert page.headers["cache-control"] == "no-store"


def test_security_headers():
    res = make_client().get("/")
    csp = res.headers["content-security-policy"]
    assert "default-src 'self'" in csp and "script-src 'self'" in csp
    assert res.headers["x-content-type-options"] == "nosniff"
    assert 'src="/static/app.js"' in res.text and "<script>" not in res.text  # no inline script


def test_empty_and_too_long_input():
    client = make_client(WebConfig(max_chars=100))
    empty = client.post("/api/check", json={"text": "   \n"})
    assert empty.status_code == 400 and empty.json()["error"] == "empty"
    long = client.post("/api/check", json={"text": "x" * 101})
    assert long.status_code == 413
    assert "at most 100" in long.json()["message"]
    page = client.post("/check", data={"text": "x" * 101})
    assert page.status_code == 413 and "this demo checks at most 100" in page.text
    assert client.post("/api/check", json={}).status_code == 400


def test_rate_limit_per_address_with_clear_message():
    client = make_client(WebConfig(rate_limit=2, rate_window=600))
    for _ in range(2):
        assert client.post("/api/check", json={"text": "No claims in here at all."}).status_code == 200
    third = client.post("/api/check", json={"text": "No claims in here at all."})
    assert third.status_code == 429
    assert int(third.headers["retry-after"]) > 0
    assert "used its 2 live checks for 10 minutes" in third.json()["message"]
    assert "bundled examples do not count" in third.json()["message"]
    # Examples are still served.
    assert client.post("/api/check", json={"example": "agent-pr"}).status_code == 200


def test_forwarded_address_is_used_only_when_trusted():
    untrusted = make_client(WebConfig(rate_limit=1))
    assert untrusted.post("/api/check", json={"text": "nothing"}, headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 200
    # Same socket peer, different header: still the same address.
    assert untrusted.post("/api/check", json={"text": "nothing"}, headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429

    trusted = make_client(WebConfig(rate_limit=1, trust_forwarded=True))
    assert trusted.post("/api/check", json={"text": "nothing"}, headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}).status_code == 200
    assert trusted.post("/api/check", json={"text": "nothing"}, headers={"X-Forwarded-For": "2.2.2.2, 10.0.0.1"}).status_code == 200
    assert trusted.post("/api/check", json={"text": "nothing"}, headers={"X-Forwarded-For": "1.1.1.1, 10.0.0.1"}).status_code == 429


def test_busy_server_answers_503():
    client = make_client(WebConfig(max_concurrent=1))
    demo = client.app.state.demo
    assert demo.gate.try_enter()  # one check is "running"
    try:
        res = client.post("/api/check", json={"text": "nothing to see"})
        assert res.status_code == 503 and res.json()["error"] == "busy"
        assert res.headers["retry-after"] == "30"
    finally:
        demo.gate.leave()
    assert client.post("/api/check", json={"text": "nothing to see"}).status_code == 200


def test_request_body_limit():
    client = make_client(WebConfig(max_chars=100))
    res = client.post("/api/check", content=b"x" * 50_000, headers={"content-type": "application/json"})
    assert res.status_code == 413 and res.json()["error"] == "request_too_large"


def test_body_without_length_is_refused():
    import asyncio

    sent = []

    async def app(scope, receive, send):  # pragma: no cover - must not be reached
        raise AssertionError("reached the app")

    async def send(message):
        sent.append(message)

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    asyncio.run(BodySizeLimit(app, 1000)({"type": "http", "method": "POST", "headers": []}, receive, send))
    assert sent[0]["status"] == 411


# ---------------------------------------------------------------- Tavily caps


def docs_extraction(statement: str) -> str:
    claim = {
        "type": "other_external", "sentences": [1], "statement": statement, "ecosystem": None, "package": None,
        "version": None, "vulnerability_id": None, "license": None, "symbol": None, "parameter": None,
        "since_version": None, "subject": "GitHub Actions", "negated": False,
    }
    return json.dumps({"claims": [claim]})


SETTINGS_WITH_MODELS = dict(
    llm_api_key="unused", extract_model="fake-extractor", judge_models=["judge-a", "judge-b"],
    adjudicator_model="big-judge", tavily_api_key="test-key",
)


def test_daily_tavily_cap_turns_new_lookups_into_unverifiable_with_a_notice():
    statement = "GitHub Actions runs at most 20 concurrent jobs on a free account."
    llm = FakeLLM({"fake-extractor": [docs_extraction(statement)]})
    client = make_client(WebConfig(tavily_daily_cap=0), settings=no_models(**SETTINGS_WITH_MODELS), llm=llm)
    res = client.post("/api/check", json={"text": statement})
    assert res.status_code == 200
    result = res.json()["results"][0]
    assert result["verdict"] == "unverifiable" and result["path"] == "none"
    assert "daily limit of 0 new documentation lookups" in result["reason"]
    assert any("daily limit of 0 new Tavily calls is used up" in n for n in res.headers.get_list("x-hearsay-notice"))
    assert [m for m, _ in llm.calls] == ["fake-extractor"]  # no judge was asked


def test_per_check_tavily_cap_notice():
    statement = "GitHub Actions runs at most 20 concurrent jobs on a free account."
    llm = FakeLLM({"fake-extractor": [docs_extraction(statement)]})
    settings = no_models(tavily_max_calls=0, **SETTINGS_WITH_MODELS)
    page = make_client(settings=settings, llm=llm).post("/check", data={"text": statement})
    assert "reached the limit of 0 new Tavily calls per check" in page.text


def test_cached_tavily_answers_bypass_the_daily_cap():
    # The bundle holds the Tavily answers for this exact claim (from the chat-answer example).
    statement = "GitHub Actions allows at most 256 jobs per workflow run in a matrix."
    quote = "A job matrix can generate a maximum of 256 jobs per workflow run."
    from support import judge_reply

    llm = FakeLLM(
        {
            "fake-extractor": [docs_extraction(statement)],
            "judge-a": [judge_reply("supported", quote)],
            "judge-b": [judge_reply("supported", quote)],
        }
    )
    client = make_client(WebConfig(tavily_daily_cap=0), settings=no_models(**SETTINGS_WITH_MODELS), llm=llm)
    data = client.post("/api/check", json={"text": statement}).json()
    assert data["results"][0]["verdict"] == "supported"
    assert data["usage"]["tavily_calls"] == 0 and data["usage"]["tavily_cache_hits"] == 2


def test_demo_tavily_counts_only_uncached_calls(tmp_path):
    from hearsay.cache import Cache
    from hearsay.http import Http
    from hearsay.models import Usage

    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, json={"results": []})

    http = Http(Cache(tmp_path), Usage(), transport=httpx.MockTransport(handler))
    daily = DailyCap(2)
    a = DemoTavily(http, "k", max_calls=10, daily=daily)
    a.search("one", ["docs.example.org"])
    a.search("one", ["docs.example.org"])  # cached: free
    b = DemoTavily(http, "k", max_calls=10, daily=daily)  # another request shares the daily budget
    b.search("two", ["docs.example.org"])
    with pytest.raises(Exception, match="daily limit of 2"):
        b.search("three", ["docs.example.org"])
    assert b.capped == "daily" and len(requests) == 2 and daily.used == 2


# ---------------------------------------------------------------- limit primitives


def test_rate_limiter_sliding_window():
    now = [1000.0]
    rl = RateLimiter(2, 60, clock=lambda: now[0])
    assert rl.hit("a") is None and rl.hit("a") is None
    wait = rl.hit("a")
    assert wait == pytest.approx(60)
    assert rl.hit("b") is None  # per key
    now[0] += 30
    assert rl.hit("a") == pytest.approx(30)
    now[0] += 31
    assert rl.hit("a") is None


def test_daily_cap_resets_at_utc_midnight():
    now = [1_760_745_599.0]  # 2025-10-17 23:59:59 UTC
    cap = DailyCap(1, clock=lambda: now[0])
    assert cap.take() and not cap.take()
    assert cap.remaining == 0
    now[0] += 2
    assert cap.remaining == 1 and cap.take()


# ---------------------------------------------------------------- views


def test_quote_is_located_in_its_passage_with_context():
    p = Passage(id=1, url="https://docs.example.org/a", section=["Mod", "f()"], text="Intro. **Changed** in 3.12: `f()` is *deprecated*. More text.")
    q = locate_quote("Changed in 3.12: f() is deprecated", [p], p.url)
    assert q is not None and q.in_context
    assert (q.before, q.quote, q.after) == ("Intro. ", "Changed in 3.12: f() is deprecated", ". More text.")
    assert q.section == "Mod > f()"
    assert locate_quote("not there at all, no", [p], p.url) is None


def test_only_http_links():
    assert safe_url("https://pypi.org/x") == "https://pypi.org/x"
    assert safe_url("javascript:alert(1)") is None
    assert safe_url(None) is None


def test_web_config_from_env():
    c = WebConfig.from_env({"HEARSAY_WEB_RATE_LIMIT": "3", "HEARSAY_WEB_TRUST_FORWARDED": "true", "HEARSAY_WEB_MAX_CHARS": "bad"})
    assert c.rate_limit == 3 and c.trust_forwarded is True and c.max_chars == 8000


def test_templates_and_static_files_use_no_external_resources():
    root = Path(__file__).parent.parent / "src" / "hearsay" / "web"
    for path in list((root / "templates").glob("*.html")) + list((root / "static").glob("*")):
        text = path.read_text()
        assert not re.search(r"(src|href)=\"https?://", text), path
        assert "@import" not in text and "\u2014" not in text, path
