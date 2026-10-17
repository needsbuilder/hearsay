import json

import pytest

from hearsay import cli
from hearsay.github import fetch_pull_request, parse_pr_spec
from hearsay.pipeline import check, check_claims
from hearsay.report import to_json, to_markdown

from support import claim, fixture_context


def test_report_totals_json_and_markdown():
    ctx = fixture_context(tavily=False)
    report = check_claims(
        [
            claim("fixes_vulnerability", "requests 2.31.0 fixes CVE-2023-32681.", package="requests",
                  version="2.31.0", vulnerability_id="CVE-2023-32681", ecosystem="pypi"),
            claim("license_is", "requests is MIT licensed.", package="requests", license="MIT", ecosystem="pypi"),
            claim("package_exists", "serde exists.", package="serde", ecosystem="crates.io"),
        ],
        context=ctx,
    )
    assert (report.totals.supported, report.totals.contradicted, report.totals.unverifiable) == (1, 1, 1)
    data = json.loads(to_json(report))
    assert data["results"][0]["path"] == "advisory"
    assert data["results"][0]["source_url"].startswith("https://api.osv.dev/")
    md = to_markdown(report)
    assert "**3 claims checked: 1 supported, 1 contradicted, 1 unverifiable.**" in md
    assert "| c2 | **CONTRADICTED** |" in md
    assert '> licenses: "Apache-2.0"' in md
    assert "—" not in md


def test_check_without_llm_uses_patterns():
    report = check("Run `pip install fastapi==0.200.0` and `npm install left-pad-hearsay-nonexistent`.",
                   context=fixture_context(tavily=False))
    assert report.extraction.method == "patterns"
    verdicts = {r.claim.package: r.verdict.value for r in report.results}
    assert verdicts == {"fastapi": "contradicted", "left-pad-hearsay-nonexistent": "contradicted"}


def test_pr_spec_parsing():
    assert parse_pr_spec("psf/requests#6447") == ("psf", "requests", 6447)
    assert parse_pr_spec("https://github.com/psf/requests/pull/6447/files") == ("psf", "requests", 6447)
    with pytest.raises(ValueError):
        parse_pr_spec("psf/requests")


def test_fetch_recorded_pull_request():
    pr = fetch_pull_request(fixture_context().http, "gesiscss/gesis_surf_backend#67")
    assert pr.title.startswith("build(deps): bump urllib3")
    assert "Bumps [urllib3]" in pr.body


def test_cli_reports_missing_model_settings(monkeypatch, capsys, tmp_path):
    monkeypatch.chdir(tmp_path)
    for var in ("HEARSAY_EXTRACT_MODEL", "HEARSAY_JUDGE_MODELS", "HEARSAY_ADJUDICATOR_MODEL", "HEARSAY_LLM_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    assert cli.main(["claim", "requests 2.31.0 fixes CVE-2023-32681"]) == 1
    assert "--no-llm" in capsys.readouterr().err


def test_placeholders_count_as_unset():
    from hearsay.config import Settings

    s = Settings.from_env({"HEARSAY_EXTRACT_MODEL": "<nemotron-model-id-for-extraction>", "HEARSAY_JUDGE_MODELS": "<a>,<b>"})
    assert s.extract_model is None and s.judge_models == []
