"""Claim extraction parsing with a fake model."""

import json

from hearsay.extract import chunk_sentences, extract_claims, split_sentences
from hearsay.models import ClaimType

from support import FakeLLM

TEXT = (
    "Bumped requests to 2.31.0, which fixes CVE-2023-32681.\n"
    "I refactored the retry helper and all tests pass.\n"
    "The `timeout` parameter of `requests.get` is documented."
)


def c(**kw):
    base = {
        "type": None, "sentences": [1], "statement": "s s s", "ecosystem": None, "package": None, "version": None,
        "vulnerability_id": None, "license": None, "symbol": None, "parameter": None, "since_version": None,
        "subject": None, "negated": False,
    }
    base.update(kw)
    return base


FIX = c(type="fixes_vulnerability", sentences=[1], statement="requests 2.31.0 fixes CVE-2023-32681.",
        ecosystem="pypi", package="requests", version="2.31.0", vulnerability_id="CVE-2023-32681")
PARAM = c(type="parameter_exists", sentences=[3], statement="requests.get accepts a timeout parameter.",
          symbol="requests.get", parameter="timeout", subject="Python")


def run(replies):
    llm = FakeLLM({"x": list(replies)})
    claims, info = extract_claims(llm, "x", TEXT)
    return claims, info, llm


def test_split_sentences_is_verbatim():
    text = "First one. Second `x` one!\n\n```python\n# json.loads accepts bytes\n```\n- bullet item here"
    units = split_sentences(text)
    assert units == ["First one.", "Second `x` one!", "# json.loads accepts bytes", "- bullet item here"]
    assert all(u in text for u in units)


def test_chunks_respect_sentence_cap():
    chunks = chunk_sentences([f"s{i}" for i in range(20)], limit=10_000, max_sentences=8)
    assert [len(ch) for ch in chunks] == [8, 8, 4]


def test_valid_output():
    claims, info, llm = run([json.dumps({"claims": [FIX, PARAM]})])
    assert [x.type for x in claims] == [ClaimType.FIXES_VULNERABILITY, ClaimType.PARAMETER_EXISTS]
    assert claims[0].source_sentence == "Bumped requests to 2.31.0, which fixes CVE-2023-32681."
    assert claims[1].source_sentence.startswith("The `timeout` parameter")
    assert [x.id for x in claims] == ["c1", "c2"]
    assert len(llm.calls) == 1 and not info.errors and not info.rejected


def test_invalid_then_repaired():
    invented = dict(FIX, version="2.32.0")  # not in the sentence
    claims, info, llm = run([json.dumps({"claims": [invented, PARAM]}), json.dumps({"claims": [FIX]})])
    assert len(llm.calls) == 2
    assert "2.32.0" in llm.calls[1][1][-1]["content"]  # the repair round names the problem
    assert {x.version for x in claims if x.version} == {"2.31.0"}
    assert len(claims) == 2  # the valid claim from round one is kept
    assert info.errors and not info.rejected


def test_garbage_twice_gives_no_claims():
    claims, info, llm = run(["I could not find any claims, sorry.", "Still not JSON"])
    assert claims == [] and len(llm.calls) == 2
    assert any("attempt 2 invalid" in e for e in info.errors)


def test_unknown_keys_and_types_are_rejected():
    bad_key = dict(PARAM, confidence=0.9)
    bad_type = dict(PARAM, type="is_true")
    claims, info, _ = run([json.dumps({"claims": [bad_key, bad_type]}), json.dumps({"claims": []})])
    assert claims == []
    assert len(info.rejected) == 0  # attempt 2 had nothing invalid; attempt 1 errors are logged
    assert "unknown keys" in info.errors[0] and "type" in info.errors[0]


def test_missing_required_field_is_rejected():
    no_version = dict(FIX, version=None)
    claims, info, _ = run([json.dumps({"claims": [no_version]}), json.dumps({"claims": [no_version]})])
    assert claims == []
    assert info.rejected and "needs: version" in info.rejected[0].errors[0]


def test_wrong_sentence_number_is_repointed_when_unambiguous():
    misnumbered = dict(PARAM, sentences=[2])
    claims, _, llm = run([json.dumps({"claims": [misnumbered]})])
    assert len(llm.calls) == 1
    assert claims[0].source_sentence.startswith("The `timeout` parameter")


def test_negative_statement_requires_negated_flag():
    neg = dict(FIX, type="affected_by_vulnerability", statement="requests 2.31.0 is no longer affected by CVE-2023-32681.")
    claims, info, _ = run([json.dumps({"claims": [neg]}), json.dumps({"claims": [dict(neg, negated=True)]})])
    assert claims[0].negated is True
    assert "negated must be true" in info.errors[0]


def test_package_exists_with_version_becomes_version_exists():
    pin = dict(FIX, type="package_exists", vulnerability_id=None, statement="requests 2.31.0 is added.")
    claims, _, _ = run([json.dumps({"claims": [pin]})])
    assert claims[0].type == ClaimType.VERSION_EXISTS


def test_duplicates_are_merged():
    claims, _, _ = run([json.dumps({"claims": [FIX, FIX]})])
    assert len(claims) == 1
