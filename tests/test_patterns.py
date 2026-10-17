from hearsay.models import ClaimType
from hearsay.patterns import extract_with_patterns, pinned_claims
from hearsay.pipeline import add_missed_pins

from support import claim


def kinds(text):
    claims, _ = extract_with_patterns(text)
    return [(c.type, c.package, c.version, c.vulnerability_id or c.license, c.ecosystem) for c in claims]


def test_fix_claim_with_to_phrase():
    assert kinds("Bumped requests to 2.31.0, which fixes CVE-2023-32681.") == [
        (ClaimType.FIXES_VULNERABILITY, "requests", "2.31.0", "CVE-2023-32681", None)
    ]


def test_install_commands():
    out = kinds("Run `npm install express@4.21.2 left-pad` first.")
    assert (ClaimType.VERSION_EXISTS, "express", "4.21.2", None, "npm") in out
    assert (ClaimType.PACKAGE_EXISTS, "left-pad", None, None, "npm") in out
    assert kinds("pip install fastapi==0.200.0")[0][:3] == (ClaimType.VERSION_EXISTS, "fastapi", "0.200.0")


def test_install_command_in_prose_stops_at_the_clause():
    out = kinds("Run pip install requests==2.31.0, which fixes CVE-2023-32681.")
    assert (ClaimType.VERSION_EXISTS, "requests", "2.31.0", None, "pypi") in out
    assert (ClaimType.FIXES_VULNERABILITY, "requests", "2.31.0", "CVE-2023-32681", "pypi") in out
    assert {p for _, p, _, _, _ in out} == {"requests"}
    assert [p for _, p, _, _, _ in kinds("pip install fastapi and uvicorn, then restart the server.")] == ["fastapi", "uvicorn"]


def test_install_command_stops_where_the_prose_starts():
    # Without punctuation: "to" starts the prose, so "get", "new" and "router" are not packages.
    assert [p for _, p, _, _, _ in kinds("Run pip install fastapi==0.200.0 to get the new router.")] == ["fastapi"]
    assert [p for _, p, _, _, _ in kinds("npm install left-pad for the string helper")] == ["left-pad"]


def test_licence_phrase_needs_one_package():
    assert kinds("The `httpx` package is BSD-3-Clause licensed.") == [
        (ClaimType.LICENSE_IS, "httpx", None, "BSD-3-Clause", None)
    ]
    assert kinds("This library is MIT licensed.") == []


def test_dependabot_bump():
    out = kinds("Bumps [urllib3](https://github.com/urllib3/urllib3) from 2.1.0 to 2.8.0.")
    assert [(k, p, v) for k, p, v, _, _ in out] == [
        (ClaimType.VERSION_EXISTS, "urllib3", "2.1.0"),
        (ClaimType.VERSION_EXISTS, "urllib3", "2.8.0"),
    ]


def test_python_version_is_not_a_package():
    assert kinds("This works on Python 3.12 and later.") == []


def test_pins_only_ignores_prose_versions():
    assert pinned_claims("Bumped requests to 2.31.0.") == []
    assert [c.package for c in pinned_claims("Added `fastapi==0.200.0`.")] == ["fastapi"]


def test_missed_pins_are_added_once():
    text = "Added `fastapi==0.200.0` and `requests==2.31.0`."
    existing = [claim("version_exists", "requests 2.31.0 exists", package="requests", version="2.31.0",
                      source_sentence=text)]
    out = add_missed_pins(existing, text)
    assert [(c.package, c.origin) for c in out] == [("requests", "llm"), ("fastapi", "pattern")]


def flags(text):
    claims, _ = extract_with_patterns(text)
    return [(c.type, c.negated) for c in claims]


def test_negation_is_detected_before_the_deciding_word():
    # bench r22
    assert flags("urllib3 1.26.17 in requirements.txt is not affected by CVE-2023-43804.") == [
        (ClaimType.AFFECTED_BY_VULNERABILITY, True)
    ]
    assert flags("Upgrading to urllib3 2.0.5 does not fix CVE-2023-43804.") == [(ClaimType.FIXES_VULNERABILITY, True)]
    assert flags("lodash 4.17.21 is no longer affected by CVE-2021-23337.") == [(ClaimType.AFFECTED_BY_VULNERABILITY, True)]
    assert flags("requests 2.30.0 isn\u2019t vulnerable to CVE-2023-32681.") == [(ClaimType.AFFECTED_BY_VULNERABILITY, True)]
    assert flags("requests 2.30.0 has never been affected by CVE-2023-32681.") == [(ClaimType.AFFECTED_BY_VULNERABILITY, True)]
    assert flags("The `httpx` package is not BSD-3-Clause licensed.") == [(ClaimType.LICENSE_IS, True)]
    assert flags("On npm, the `express` package is not deprecated.") == [(ClaimType.DEPRECATED, True)]


def test_positive_sentences_stay_positive():
    assert flags("urllib3 2.0.6 fixes CVE-2023-43804.") == [(ClaimType.FIXES_VULNERABILITY, False)]
    assert flags("lodash 4.17.20 is affected by CVE-2021-23337.") == [(ClaimType.AFFECTED_BY_VULNERABILITY, False)]
    # a "not" in another clause does not flip the claim
    assert flags("requests 2.31.0 fixes CVE-2023-32681; the old pin was not patched.") == [
        (ClaimType.FIXES_VULNERABILITY, False)
    ]
    assert flags("The `httpx` package is BSD-3-Clause licensed.") == [(ClaimType.LICENSE_IS, False)]


def test_negated_pattern_claim_end_to_end():
    from hearsay.pipeline import check

    from support import fixture_context

    report = check("urllib3 1.26.17 in requirements.txt is not affected by CVE-2023-43804.",
                   context=fixture_context(tavily=False))
    assert [(r.claim.negated, r.verdict.value) for r in report.results] == [(True, "supported")]
