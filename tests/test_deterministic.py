"""Registry and advisory checks against recorded PyPI, npm, deps.dev and OSV responses."""

import pytest

from hearsay.models import DecisionPath, Verdict
from hearsay.pipeline import check_claim

from support import claim, fixture_context


@pytest.fixture
def ctx():
    return fixture_context(tavily=False)


def run(ctx, kind, **fields):
    return check_claim(ctx, claim(kind, **fields))


# ---------------------------------------------------------------- package_exists


def test_package_exists_true(ctx):
    r = run(ctx, "package_exists", package="requests", ecosystem="pypi")
    assert r.verdict == Verdict.SUPPORTED
    assert r.path == DecisionPath.REGISTRY
    assert r.source_url == "https://pypi.org/pypi/requests/json"
    assert 'info.name: "requests"' in r.quote


def test_package_exists_false_on_both_registries(ctx):
    r = run(ctx, "package_exists", package="pydantic-settings-extra")
    assert r.verdict == Verdict.CONTRADICTED
    assert "PyPI: HTTP 404" in r.quote and "npm: HTTP 404" in r.quote


def test_package_exists_false_npm(ctx):
    r = run(ctx, "package_exists", package="left-pad-hearsay-nonexistent", ecosystem="npm")
    assert r.verdict == Verdict.CONTRADICTED
    assert r.source_url == "https://registry.npmjs.org/left-pad-hearsay-nonexistent"


def test_package_exists_unknown_ecosystem(ctx):
    r = run(ctx, "package_exists", package="serde", ecosystem="crates.io")
    assert r.verdict == Verdict.UNVERIFIABLE
    assert "not supported" in r.reason


def test_negated_package_claim_flips(ctx):
    r = run(ctx, "package_exists", package="left-pad-hearsay-nonexistent", ecosystem="npm", negated=True)
    assert r.verdict == Verdict.SUPPORTED
    assert any("negated" in n for n in r.notes)


# ---------------------------------------------------------------- version_exists


def test_version_exists_true_with_pep440_equality(ctx):
    r = run(ctx, "version_exists", package="requests", version="2.31", ecosystem="pypi")
    assert r.verdict == Verdict.SUPPORTED
    assert any("2.31.0" in n for n in r.notes)


def test_version_exists_yanked_is_noted(ctx):
    r = run(ctx, "version_exists", package="requests", version="2.32.0", ecosystem="pypi")
    assert r.verdict == Verdict.SUPPORTED
    assert any("yanked" in n for n in r.notes)


def test_version_exists_false(ctx):
    r = run(ctx, "version_exists", package="requests", version="2.99.0", ecosystem="pypi")
    assert r.verdict == Verdict.CONTRADICTED
    assert 'releases has no key "2.99.0"' in r.quote


def test_version_exists_npm_true_and_false(ctx):
    assert run(ctx, "version_exists", package="express", version="4.21.2", ecosystem="npm").verdict == Verdict.SUPPORTED
    r = run(ctx, "version_exists", package="express", version="9.9.9", ecosystem="npm")
    assert r.verdict == Verdict.CONTRADICTED
    assert r.quote.startswith('versions has no key "9.9.9"')


def test_version_exists_invalid_version_is_unverifiable(ctx):
    r = run(ctx, "version_exists", package="requests", version="latest-ish", ecosystem="pypi")
    assert r.verdict == Verdict.UNVERIFIABLE


# ---------------------------------------------------------------- vulnerabilities


def test_fixes_vulnerability_true(ctx):
    r = run(ctx, "fixes_vulnerability", package="requests", version="2.31.0", vulnerability_id="CVE-2023-32681", ecosystem="pypi")
    assert r.verdict == Verdict.SUPPORTED
    assert r.path == DecisionPath.ADVISORY
    assert r.source_url == "https://api.osv.dev/v1/vulns/GHSA-j8r2-6x86-q33q"
    assert '{"fixed": "2.31.0"}' in r.quote
    assert "first fixed release" in r.reason


def test_fixes_vulnerability_false_still_affected(ctx):
    r = run(ctx, "fixes_vulnerability", package="urllib3", version="1.26.5", vulnerability_id="CVE-2023-43804", ecosystem="pypi")
    assert r.verdict == Verdict.CONTRADICTED
    assert "1.26.17" in r.reason


def test_fixes_vulnerability_false_version_predates_bug(ctx):
    r = run(ctx, "fixes_vulnerability", package="requests", version="2.0.0", vulnerability_id="CVE-2023-32681", ecosystem="pypi")
    assert r.verdict == Verdict.CONTRADICTED
    assert "predates" in r.reason


def test_fixes_vulnerability_unknown_when_not_linked_to_package(ctx):
    r = run(ctx, "fixes_vulnerability", package="urllib3", version="1.26.18", vulnerability_id="CVE-2023-32681", ecosystem="pypi")
    assert r.verdict == Verdict.UNVERIFIABLE
    assert "not linked" in r.reason


def test_fixes_vulnerability_unknown_id(ctx):
    r = run(ctx, "fixes_vulnerability", package="requests", version="2.31.0", vulnerability_id="CVE-2099-0001", ecosystem="pypi")
    assert r.verdict == Verdict.UNVERIFIABLE
    assert "no record" in r.reason


def test_affected_true(ctx):
    r = run(ctx, "affected_by_vulnerability", package="requests", version="2.30.0", vulnerability_id="CVE-2023-32681", ecosystem="pypi")
    assert r.verdict == Verdict.SUPPORTED


def test_alias_merged_record_of_another_cve_is_not_used(ctx):
    # OSV merges aliases: the 2026 incomplete-fix advisory GHSA-r5fr also lists CVE-2021-23337.
    # GitHub wrote GHSA-r5fr for a CVE published at NVD in 2026, so it is not this CVE's record.
    r = run(ctx, "affected_by_vulnerability", package="lodash", version="4.17.21", vulnerability_id="CVE-2021-23337", ecosystem="npm")
    assert r.verdict == Verdict.CONTRADICTED
    assert r.source_url.endswith("GHSA-35jh-r3h4-6jhm")
    assert any(n.startswith("GHSA-r5fr-rjxr-66jc is not used") for n in r.notes)


def test_r13_later_cve_follows_its_own_advisory(ctx):
    # bench r13: no record's own id is CVE-2026-4800 and the 2021 record lists it too.
    r = run(ctx, "affected_by_vulnerability", package="lodash", version="4.17.21", vulnerability_id="CVE-2026-4800", ecosystem="npm")
    assert r.verdict == Verdict.SUPPORTED
    assert r.source_url.endswith("GHSA-r5fr-rjxr-66jc")
    assert '{"fixed": "4.18.0"}' in r.quote
    assert any(n.startswith("GHSA-35jh-r3h4-6jhm is not used") and "2021-02-15" in n for n in r.notes)


def test_r12_fix_of_the_older_cve_is_supported(ctx):
    r = run(ctx, "fixes_vulnerability", package="lodash", version="4.17.21", vulnerability_id="CVE-2021-23337", ecosystem="npm")
    assert r.verdict == Verdict.SUPPORTED
    assert "first fixed release" in r.reason


def test_u01_matching_records_that_disagree_give_unverifiable(ctx):
    # bench u01: GitHub's record starts at 2.0.0rc1, PYSEC-2023-221 at 0. Both describe the CVE.
    r = run(ctx, "affected_by_vulnerability", package="werkzeug", version="1.0.1", vulnerability_id="CVE-2023-46136", ecosystem="pypi")
    assert r.verdict == Verdict.UNVERIFIABLE
    assert r.path == DecisionPath.ADVISORY
    assert "disagree" in r.reason
    assert "GHSA-hrfv-mqp8-q5rw says not affected" in r.reason
    assert "PYSEC-2023-221 says affected" in r.reason
    assert '{"introduced": "2.0.0rc1"}' in r.quote and '{"introduced": "0"}' in r.quote


def test_matching_rule_needs_github_date_evidence():
    from hearsay.deterministic import _other_cve

    cve = {"id": "CVE-2026-4800", "published": "2026-03-31T19:25:55.987Z"}
    old = {"id": "GHSA-old", "database_specific": {"nvd_published_at": "2021-02-15T13:15:00Z"}}
    same = {"id": "GHSA-new", "database_specific": {"nvd_published_at": "2026-04-02T00:00:00Z"}}
    pysec = {"id": "PYSEC-2021-1", "published": "2021-02-20T00:00:00Z"}
    assert "is not used" in _other_cve(old, "CVE-2026-4800", cve)
    assert _other_cve(same, "CVE-2026-4800", cve) is None  # within 7 days
    assert _other_cve(pysec, "CVE-2026-4800", cve) is None  # no evidence: kept
    assert _other_cve(old, "CVE-2026-4800", None) is None  # CVE record unknown: kept


def test_affected_npm_true(ctx):
    r = run(ctx, "affected_by_vulnerability", package="lodash", version="4.17.20", vulnerability_id="CVE-2021-23337", ecosystem="npm")
    assert r.verdict == Verdict.SUPPORTED


def test_affected_without_id_lists_advisories(ctx):
    r = run(ctx, "affected_by_vulnerability", package="requests", version="2.31.0", ecosystem="pypi")
    assert r.verdict == Verdict.SUPPORTED
    assert r.quote.startswith("vulns[].id:")


def test_negated_not_affected(ctx):
    r = run(ctx, "affected_by_vulnerability", package="urllib3", version="1.26.17", vulnerability_id="CVE-2023-43804",
            ecosystem="pypi", negated=True)
    assert r.verdict == Verdict.SUPPORTED


def test_negated_no_known_vulnerabilities(ctx):
    r = run(ctx, "affected_by_vulnerability", package="requests", version="2.33.0", ecosystem="pypi", negated=True)
    assert r.verdict == Verdict.SUPPORTED
    assert "vulns: []" in r.quote


# ---------------------------------------------------------------- licence


def test_license_false(ctx):
    r = run(ctx, "license_is", package="requests", license="MIT", ecosystem="pypi")
    assert r.verdict == Verdict.CONTRADICTED
    assert r.source_url.startswith("https://api.deps.dev/")
    assert r.quote == 'licenses: "Apache-2.0"'


def test_license_true_with_alias(ctx):
    assert run(ctx, "license_is", package="requests", license="Apache 2.0", ecosystem="pypi").verdict == Verdict.SUPPORTED
    assert run(ctx, "license_is", package="httpx", license="BSD-3-Clause", ecosystem="pypi").verdict == Verdict.SUPPORTED
    assert run(ctx, "license_is", package="httpx", license="BSD", ecosystem="pypi").verdict == Verdict.SUPPORTED


def test_license_npm_specific_version(ctx):
    r = run(ctx, "license_is", package="express", version="5.0.0", license="MIT", ecosystem="npm")
    assert r.verdict == Verdict.SUPPORTED


def test_license_unknown_when_ecosystem_ambiguous(ctx):
    r = run(ctx, "license_is", package="requests", license="MIT")
    assert r.verdict == Verdict.UNVERIFIABLE
    assert "both PyPI and npm" in r.reason


# ---------------------------------------------------------------- npm deprecation


def test_npm_deprecated_true(ctx):
    r = run(ctx, "deprecated", package="left-pad", ecosystem="npm")
    assert r.verdict == Verdict.SUPPORTED
    assert r.path == DecisionPath.REGISTRY
    assert "padStart" in r.quote


def test_npm_not_deprecated_falls_through_to_docs(ctx):
    # No deprecated field: the registry does not settle it, so the claim goes
    # to the docs path, which is unavailable here.
    r = run(ctx, "deprecated", package="express", ecosystem="npm")
    assert r.verdict == Verdict.UNVERIFIABLE
    assert r.path == DecisionPath.NONE
