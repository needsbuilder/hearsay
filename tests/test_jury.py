"""Jury aggregation with a fake model: agreement, disagreement, invalid quotes, invalid output."""

from hearsay.jury import run_jury
from hearsay.models import DecisionPath, Passage, Verdict

from support import FakeLLM, claim, judge_reply

URL = "https://docs.python.org/3/library/datetime.html"
PASSAGES = [
    Passage(id=1, url="https://docs.python.org/3/whatsnew/3.12.html", text="Other changes in this release."),
    Passage(
        id=2,
        url=URL,
        text="classmethod datetime.utcnow()\n\nReturn the current UTC date and time.\n\n"
        "Deprecated since version 3.12: Use datetime.now() with UTC instead.",
    ),
]
GOOD = "Deprecated since version 3.12: Use datetime.now() with UTC instead."
CLAIM = claim(
    "deprecated", "datetime.utcnow() is deprecated since Python 3.12.", symbol="datetime.utcnow()", since_version="3.12"
)


def jury(script):
    llm = FakeLLM(script)
    return run_jury(llm, ["judge-a", "judge-b"], "big", CLAIM, PASSAGES), llm


def test_unanimous_supported_uses_jury_path():
    out, llm = jury({"judge-a": [judge_reply("supported", GOOD, URL)], "judge-b": [judge_reply("supported", GOOD)]})
    assert out.verdict == Verdict.SUPPORTED
    assert out.path == DecisionPath.JURY
    assert out.url == URL  # located from the quote even when a judge gives no URL
    assert out.adjudicator is None
    assert [m for m, _ in llm.calls] == ["judge-a", "judge-b"]


def test_judges_do_not_see_each_other():
    out, llm = jury({"judge-a": [judge_reply("supported", GOOD)], "judge-b": [judge_reply("supported", GOOD)]})
    assert llm.calls[0][1] == llm.calls[1][1]


def test_disagreement_goes_to_adjudicator():
    out, llm = jury(
        {
            "judge-a": [judge_reply("supported", GOOD)],
            "judge-b": [judge_reply("unverifiable", "")],
            "big": [judge_reply("supported", GOOD, URL, "the excerpt says so")],
        }
    )
    assert out.path == DecisionPath.ADJUDICATOR
    assert out.verdict == Verdict.SUPPORTED
    assert out.adjudicator.model == "big"
    adjudicator_prompt = llm.calls[-1][1][-1]["content"]
    assert "Judge 1: supported" in adjudicator_prompt and "Judge 2: unverifiable" in adjudicator_prompt


def test_adjudicator_quote_rule_applies():
    out, _ = jury(
        {
            "judge-a": [judge_reply("supported", GOOD)],
            "judge-b": [judge_reply("contradicted", "Return the current UTC date and time.")],
            "big": [judge_reply("contradicted", "utcnow was removed in Python 3.12 entirely")],
        }
    )
    assert out.path == DecisionPath.ADJUDICATOR
    assert out.verdict == Verdict.UNVERIFIABLE
    assert out.quote is None
    assert "does not appear" in out.adjudicator.error


def test_all_quotes_invalid_means_unverifiable():
    out, llm = jury(
        {
            "judge-a": [judge_reply("supported", "utcnow() is deprecated since Python 3.12")],
            "judge-b": [judge_reply("supported", "Deprecated since 3.12, use now() instead")],
        }
    )
    assert out.verdict == Verdict.UNVERIFIABLE
    assert out.path == DecisionPath.JURY  # judges agree once the quote rule is applied
    assert all(not v.quote_found and v.stated_verdict == Verdict.SUPPORTED for v in out.votes)
    assert "quotes were not in the evidence" in out.reason
    assert "big" not in [m for m, _ in llm.calls]


def test_invalid_output_is_repaired_once():
    out, llm = jury(
        {
            "judge-a": ["Sure! The claim is supported.", judge_reply("supported", GOOD)],
            "judge-b": [judge_reply("supported", GOOD)],
        }
    )
    assert out.verdict == Verdict.SUPPORTED
    assert len([m for m, _ in llm.calls if m == "judge-a"]) == 2
    assert "invalid" in llm.calls[1][1][-1]["content"]


def test_output_invalid_twice_counts_as_unverifiable_vote():
    out, _ = jury(
        {
            "judge-a": ['{"verdict": "probably"}', '{"verdict": "supported", "confidence": 0.9}'],
            "judge-b": [judge_reply("unverifiable")],
        }
    )
    vote = out.votes[0]
    assert vote.stated_verdict is None and vote.verdict == Verdict.UNVERIFIABLE
    assert "invalid output" in vote.error
    assert out.verdict == Verdict.UNVERIFIABLE and out.path == DecisionPath.JURY


def test_supported_without_quote_is_discarded():
    out, _ = jury({"judge-a": [judge_reply("supported", "")], "judge-b": [judge_reply("unverifiable")]})
    assert out.votes[0].verdict == Verdict.UNVERIFIABLE
    assert "no quote" in out.votes[0].error


def test_reasoning_block_and_fences_are_tolerated():
    wrapped = "<think>let me see</think>\n```json\n" + judge_reply("supported", GOOD) + "\n```"
    out, _ = jury({"judge-a": [wrapped], "judge-b": [judge_reply("supported", GOOD)]})
    assert out.verdict == Verdict.SUPPORTED
