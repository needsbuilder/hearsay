"""Docs path: official domain resolution, Tavily (recorded responses), passage selection, jury (fake)."""

from hearsay.docs import check_docs_claim, docs_query
from hearsay.docs_domain import resolve_docs
from hearsay.models import DecisionPath, Verdict
from hearsay.passages import select_passages, split_passages

from support import FakeLLM, claim, docs_claim, fixture_context, judge_reply


def test_domain_from_pypi_documentation_url():
    ctx = fixture_context()
    target = resolve_docs(ctx.http, docs_claim("requests_timeout"))
    assert target.domains == ["requests.readthedocs.io"]
    assert "PyPI metadata" in target.how


def test_domain_for_stdlib_and_curated_vendors():
    ctx = fixture_context()
    assert resolve_docs(ctx.http, docs_claim("utcnow")).domains == ["docs.python.org"]
    assert resolve_docs(ctx.http, docs_claim("github_matrix")).domains == ["docs.github.com"]
    stripe = claim("api_behavior", "Stripe refunds accept an idempotency key.", subject="Stripe API")
    assert resolve_docs(ctx.http, stripe).domains == ["docs.stripe.com", "stripe.com"]
    at = claim("api_behavior", "Array.prototype.at() accepts negative integers.", symbol="Array.prototype.at()")
    assert resolve_docs(ctx.http, at).domains == ["developer.mozilla.org"]
    rm = claim("parameter_exists", "fs.rm has recursive.", symbol="fs.rm", parameter="recursive", subject="Node.js")
    assert resolve_docs(ctx.http, rm).domains == ["nodejs.org"]


def test_no_documentation_source_is_unverifiable_without_calls():
    ctx = fixture_context(llm=FakeLLM({}))
    vague = claim("other_external", "Most teams prefer httpx over requests these days.")
    r = check_docs_claim(ctx, vague)
    assert r.verdict == Verdict.UNVERIFIABLE and r.path == DecisionPath.NONE
    assert ctx.usage.tavily_calls == 0 and ctx.usage.tavily_cache_hits == 0


def test_query_shapes():
    assert docs_query(docs_claim("requests_timeout")) == "requests.get timeout parameter"
    assert docs_query(docs_claim("utcnow")) == "datetime.utcnow() deprecated 3.12"


def test_docs_claim_end_to_end_on_recorded_tavily_data():
    quote = "A job matrix can generate a maximum of 256 jobs per workflow run."
    llm = FakeLLM({"judge-a": [judge_reply("supported", quote)], "judge-b": [judge_reply("supported", quote)]})
    ctx = fixture_context(llm=llm)
    r = check_docs_claim(ctx, docs_claim("github_matrix"))
    assert r.verdict == Verdict.SUPPORTED
    assert r.path == DecisionPath.JURY
    assert r.source_url.startswith("https://docs.github.com/")
    assert r.docs_domains == ["docs.github.com"]
    assert 1 <= len(r.evidence) <= 6
    assert all(p.url.startswith("https://docs.github.com/") for p in r.evidence)
    # search + extract answered from the recorded cache
    assert ctx.usage.tavily_cache_hits == 2 and ctx.usage.tavily_calls == 0
    # the judges saw the passages, and not the input sentence
    prompt = llm.calls[0][1][-1]["content"]
    assert "256 jobs" in prompt and "Sentence it came from" not in prompt


def test_hallucinated_quote_on_real_evidence_is_unverifiable():
    fake = "GitHub Actions matrices are limited to 256 jobs in total."
    llm = FakeLLM({"judge-a": [judge_reply("supported", fake)], "judge-b": [judge_reply("supported", fake)]})
    r = check_docs_claim(fixture_context(llm=llm), docs_claim("github_matrix"))
    assert r.verdict == Verdict.UNVERIFIABLE
    assert all(v.stated_verdict == Verdict.SUPPORTED and not v.quote_found for v in r.judges)


def test_passage_selection_keeps_relevant_text_small():
    claim_ = docs_claim("requests_timeout")
    page = "\n\n".join(["Unrelated paragraph about cookies and sessions." * 3] * 10 + ["Use the timeout parameter with requests.get."])
    passages = select_passages([("https://x.example/a", "", page)], claim_, max_passages=3)
    assert passages[0].text == "Use the timeout parameter with requests.get."
    assert sum(len(p.text) for p in passages) <= 4500


def test_tavily_chunk_separator_splits_passages():
    pieces = split_passages("First chunk text here. [...] Second chunk text here.")
    assert pieces == ["First chunk text here.", "Second chunk text here."]
