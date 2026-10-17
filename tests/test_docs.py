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


# ---------------------------------------------------------------- anchoring on recorded pages

from hearsay.anchoring import Anchor  # noqa: E402
from hearsay.docs import fetch_pages  # noqa: E402
from hearsay.docs_domain import resolve_docs as _resolve  # noqa: E402
from hearsay.jury import run_jury  # noqa: E402
from hearsay.passages import page_windows  # noqa: E402

RMDIR_LINE = "v25.0.0 | Remove `recursive` option."
RM_RECURSIVE = "`recursive` If `true`, perform a recursive removal."


def recorded_windows(name):
    """Windows of the pages recorded for a docs claim (Tavily Search + Extract replayed)."""
    ctx = fixture_context()
    c = docs_claim(name)
    pages = fetch_pages(ctx, c, _resolve(ctx.http, c), [])
    assert ctx.usage.tavily_cache_hits == 2 and ctx.usage.tavily_calls == 0
    return c, [w for url, title, text in pages for w in page_windows(url, title, text)]


def pick(windows, api_heading_start, text_part):
    w = next(w for w in windows if (w.api_heading or "").startswith(api_heading_start) and text_part in w.text)
    return w


def test_fs_rm_old_failure_is_no_longer_contradicted():
    # The stand-in's earlier failure, replayed: one judge cites fs.rm, one judge and the
    # adjudicator cite the fs.rmdir version history. The rmdir passage is in the evidence.
    c, windows = recorded_windows("fs_rm")
    rmdir = pick(windows, "fs.rmdir(", RMDIR_LINE)
    rm = pick(windows, "fs.rm(", "perform a recursive removal")
    passages = [rmdir.as_passage(1), rm.as_passage(2)]
    assert "use `fs.rm` instead" in rmdir.text  # the rmdir text even names fs.rm: the heading decides
    llm = FakeLLM(
        {
            "judge-a": [judge_reply("supported", RM_RECURSIVE)],
            "judge-b": [judge_reply("contradicted", RMDIR_LINE)],
            "big": [judge_reply("contradicted", RMDIR_LINE)],
        }
    )
    out = run_jury(llm, ["judge-a", "judge-b"], "big", c, passages, Anchor.for_claim(c))
    assert out.verdict == Verdict.UNVERIFIABLE  # the adjudicator's only quote is not about fs.rm
    assert out.verdict != Verdict.CONTRADICTED
    b = out.votes[1]
    assert b.quote_found and b.anchored is False and b.verdict == Verdict.UNVERIFIABLE
    assert "anchoring: the quote is in the section for 'fs.rmdir(path[, options], callback)'" in b.error
    assert out.votes[0].anchored is True and out.votes[0].verdict == Verdict.SUPPORTED


def test_fs_rm_end_to_end_is_supported_by_its_own_section():
    llm = FakeLLM(
        {
            "judge-a": [judge_reply("supported", RM_RECURSIVE)],
            "judge-b": [judge_reply("contradicted", RMDIR_LINE)],
            "big": [judge_reply("supported", RM_RECURSIVE)],
        }
    )
    ctx = fixture_context(llm=llm, adjudicator="big")
    r = check_docs_claim(ctx, docs_claim("fs_rm"))
    assert r.verdict == Verdict.SUPPORTED
    assert r.source_url == "https://nodejs.org/api/fs.html"
    anchor = Anchor.for_claim(r.claim)
    assert anchor.problem(r.evidence[0]) is None  # windows about fs.rm rank first
    assert any((p.api_heading or "").startswith("fs.rm(") for p in r.evidence)
    assert all(p.section for p in r.evidence)
    assert "Section: " in llm.calls[0][1][-1]["content"]  # judges see the heading path
    assert r.judges[1].verdict == Verdict.UNVERIFIABLE  # rmdir quote: absent or not anchored


def test_python_symbol_anchoring_positive_and_negative():
    c, windows = recorded_windows("utcnow")
    utcnow = pick(windows, "classmethod datetime.utcnow()", "Deprecated since version 3.12")
    sibling = pick(windows, "classmethod datetime.utcfromtimestamp(", "Deprecated since version 3.12")
    now = pick(windows, "classmethod datetime.now(", "preferred over")
    passages = [utcnow.as_passage(1), sibling.as_passage(2), now.as_passage(3)]
    anchor = Anchor.for_claim(c)

    good = "Deprecated since version 3.12: Use `datetime.now()` with `UTC` instead."
    out = run_jury(FakeLLM({"judge-a": [judge_reply("supported", good)], "judge-b": [judge_reply("supported", good)]}),
                   ["judge-a", "judge-b"], "big", c, passages, anchor)
    assert out.verdict == Verdict.SUPPORTED and all(v.anchored for v in out.votes)

    # Same deprecation wording, but in the section for a different method.
    wrong = "Deprecated since version 3.12: Use `datetime.fromtimestamp()` with `UTC` instead."
    # A different method whose text links to utcnow(): the heading still decides.
    mention = "This function is preferred over"
    out = run_jury(FakeLLM({"judge-a": [judge_reply("supported", wrong)], "judge-b": [judge_reply("supported", mention + " [`today()`]")]}),
                   ["judge-a", "judge-b"], "big", c, passages, anchor)
    assert out.verdict == Verdict.UNVERIFIABLE
    a = out.votes[0]
    assert a.quote_found and a.anchored is False and "utcfromtimestamp" in a.error
    assert "their quotes came from sections about something else" in out.reason or out.votes[1].anchored is not True
