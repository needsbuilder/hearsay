"""MCP server tools, called through an in-process MCP client. No network, no model calls."""

import json

import anyio
from mcp import Client

from hearsay.mcp_server import CheckOutput, build_server, default_context, run_check, summarize

from support import FakeLLM, fixture_context


def extraction(*claims) -> str:
    base = {
        "ecosystem": None, "package": None, "version": None, "vulnerability_id": None, "license": None,
        "symbol": None, "parameter": None, "since_version": None, "subject": None, "negated": False,
    }
    return json.dumps({"claims": [{**base, **c} for c in claims]})


FIX = dict(type="fixes_vulnerability", sentences=[1], statement="requests 2.31.0 fixes CVE-2023-32681.",
           ecosystem="pypi", package="requests", version="2.31.0", vulnerability_id="CVE-2023-32681")
MIT = dict(type="license_is", sentences=[2], statement="requests is MIT licensed.",
           ecosystem="pypi", package="requests", license="MIT")


def factory_with(*replies, notes=()):
    """Each tool call gets a fresh fixture context whose extractor answers `replies` in order."""
    llm = FakeLLM({"fake-extractor": list(replies)})

    def factory():
        return fixture_context(llm=llm, tavily=False), list(notes)

    return factory, llm


def call(server, tool, args):
    async def go():
        async with Client(server) as client:
            return await client.call_tool(tool, args)

    return anyio.run(go)


def test_tools_are_listed_with_output_schemas_and_read_only_hints():
    async def go():
        async with Client(build_server(lambda: (fixture_context(), []))) as client:
            return (await client.list_tools()).tools

    tools = {t.name: t for t in anyio.run(go)}
    assert set(tools) == {"hearsay_check", "hearsay_claim"}
    for t in tools.values():
        assert t.annotations.read_only_hint is True and t.annotations.destructive_hint is False
        props = t.output_schema["properties"]
        assert {"totals", "claims", "models_used", "notes"} <= set(props)
    assert tools["hearsay_claim"].input_schema["required"] == ["sentence"]
    assert tools["hearsay_check"].input_schema["required"] == ["text"]


def test_hearsay_claim_returns_structured_verdict_and_summary():
    factory, llm = factory_with(extraction(FIX))
    result = call(build_server(factory), "hearsay_claim", {"sentence": "requests 2.31.0 fixes CVE-2023-32681."})
    assert not result.is_error
    data = result.structured_content
    assert data["totals"] == {"claims": 1, "supported": 1, "contradicted": 0, "unverifiable": 0}
    claim = data["claims"][0]
    assert claim["verdict"] == "supported" and claim["path"] == "advisory"
    assert claim["source_url"].startswith("https://api.osv.dev/")
    assert claim["quote"].startswith("affected[requests].ranges.events")
    assert data["models_used"] is True
    text = result.content[0].text
    assert text.startswith("1 claim: 1 supported, 0 contradicted, 0 unverifiable.")
    assert "SUPPORTED (advisory): requests 2.31.0 fixes CVE-2023-32681." in text
    assert len(llm.calls) == 1


def test_hearsay_check_reports_a_contradiction():
    factory, _ = factory_with(extraction(FIX, MIT))
    text = "Bumped requests to 2.31.0, which fixes CVE-2023-32681.\nThe requests library is MIT licensed."
    result = call(build_server(factory), "hearsay_check", {"text": text})
    verdicts = [(c["statement"], c["verdict"], c["path"]) for c in result.structured_content["claims"]]
    assert verdicts == [
        ("requests 2.31.0 fixes CVE-2023-32681.", "supported", "advisory"),
        ("requests is MIT licensed.", "contradicted", "registry"),
    ]
    assert "CONTRADICTED (registry): requests is MIT licensed." in result.content[0].text


def test_empty_input_is_a_tool_error():
    result = call(build_server(lambda: (fixture_context(), [])), "hearsay_check", {"text": "  "})
    assert result.is_error and "Give some text" in result.content[0].text


def test_without_model_settings_the_tools_use_patterns_and_say_so(monkeypatch):
    for var in ("HEARSAY_EXTRACT_MODEL", "HEARSAY_JUDGE_MODELS", "HEARSAY_ADJUDICATOR_MODEL", "HEARSAY_LLM_API_KEY", "TAVILY_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HEARSAY_CACHE_DIR", "off")
    ctx, notes = default_context()
    try:
        assert ctx.llm is None and ctx.tavily is None
        assert "Model settings are missing" in notes[0]
    finally:
        ctx.close()

    def patterns_factory():
        return fixture_context(tavily=False), notes

    out = run_check("Run `pip install fastapi==0.200.0` first.", patterns_factory)
    assert out.models_used is False
    assert [(c.statement, c.verdict) for c in out.claims] == [("fastapi 0.200.0 is published on PyPI.", "contradicted")]
    assert "Note: Model settings are missing" in summarize(out)


def test_summary_without_claims():
    out = CheckOutput(totals={"claims": 0, "supported": 0, "contradicted": 0, "unverifiable": 0}, claims=[], models_used=True)
    assert summarize(out) == "No checkable claims about third-party facts were found."
