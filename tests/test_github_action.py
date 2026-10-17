"""The GitHub Action's script: event parsing, comment rendering, comment upsert. No network, no model calls."""

import json
import re
from pathlib import Path

import httpx
import pytest

from hearsay import github_action as ga
from hearsay.pipeline import check_claims

from support import FakeLLM, claim, fixture_context

ROOT = Path(__file__).parent.parent
EVENTS = Path(__file__).parent / "fixtures" / "action"


def small_report():
    return check_claims(
        [
            claim("fixes_vulnerability", "requests 2.31.0 fixes CVE-2023-32681.", package="requests",
                  version="2.31.0", vulnerability_id="CVE-2023-32681", ecosystem="pypi"),
            claim("license_is", "requests is MIT licensed.", package="requests", license="MIT", ecosystem="pypi"),
        ],
        context=fixture_context(tavily=False),
    )


PR = ga.PullRequest("o/r", 7, "Bump requests", "body", "https://github.com/o/r/pull/7")


# ---------------------------------------------------------------- event


def test_pull_request_event():
    event = json.loads((EVENTS / "pull_request.json").read_text())
    pr = ga.pull_request_from_event(event)
    assert (pr.repo, pr.number) == ("example-org/payments-service", 42)
    assert pr.title == "Pin patched dependencies and make refunds retry-safe"
    assert "Bumped `requests` to 2.31.0" in pr.body


def test_issue_comment_event_on_a_pull_request_and_on_an_issue():
    event = json.loads((EVENTS / "issue_comment.json").read_text())
    pr = ga.pull_request_from_event(event)
    assert pr.number == 42 and "Bumped `requests`" in pr.body
    del event["issue"]["pull_request"]
    assert ga.pull_request_from_event(event) is None


def test_agent_comments_are_bots_or_listed_logins_and_never_hearsay_itself():
    comments = [
        {"user": {"login": "devin-ai-integration[bot]", "type": "Bot"}, "body": "requests 2.31.0 fixes it", "html_url": "u1"},
        {"user": {"login": "alice", "type": "User"}, "body": "looks good", "html_url": "u2"},
        {"user": {"login": "agent-sam", "type": "User"}, "body": "lodash 4.17.21 is fine", "html_url": "u3"},
        {"user": {"login": "github-actions[bot]", "type": "Bot"}, "body": f"{ga.MARKER}\nold report", "html_url": "u4"},
        {"user": {"login": "renovate[bot]", "type": "Bot"}, "body": "   ", "html_url": "u5"},
    ]
    picked = ga.agent_comments(comments, {"agent-sam"})
    assert [c.author for c in picked] == ["devin-ai-integration[bot]", "agent-sam"]
    text = ga.build_input(PR, picked)
    assert text.startswith("Bump requests\n\nbody")
    assert "Comment by @agent-sam:\n\nlodash 4.17.21 is fine" in text
    assert ga.is_agent({"login": "Copilot", "type": "User"}, {"copilot"})


def test_options_from_inputs():
    opts = ga.Options.from_env({"HEARSAY_ACTION_FAIL_ON_CONTRADICTED": "true", "HEARSAY_ACTION_AGENT_LOGINS": " Agent-Sam , bot2 ",
                                "HEARSAY_ACTION_INCLUDE_BOT_COMMENTS": "false"})
    assert opts.fail_on_contradicted and not opts.include_bot_comments and not opts.comment_on_empty
    assert opts.agent_logins == {"agent-sam", "bot2"}


# ---------------------------------------------------------------- comment rendering


def test_comment_has_marker_report_scope_and_run_link():
    report = small_report()
    comments = [ga.AgentComment("devin-ai-integration[bot]", "x", "u")]
    body = ga.render_comment(report, PR, comments=comments, notes=["A note."], run_url="https://github.com/o/r/actions/runs/1")
    assert body.startswith(ga.MARKER + "\n## Hearsay: claims about the outside world")
    assert "**2 claims checked: 1 supported, 1 contradicted, 0 unverifiable.**" in body
    assert "| c2 | **CONTRADICTED** | requests is MIT licensed. | registry |" in body
    assert "Checked the pull request description and 1 comment by @devin-ai-integration[bot]." in body
    assert "A note." in body and "[Workflow run](https://github.com/o/r/actions/runs/1)" in body
    assert "\u2014" not in body


def test_long_report_falls_back_to_the_table_and_then_a_hard_cut():
    report = small_report()
    full = ga.render_comment(report, PR)
    short = ga.render_comment(report, PR, limit=len(full) - 1)
    assert len(short) < len(full)
    assert "| c1 | **SUPPORTED** |" in short and "### c1." not in short
    assert "did not fit in one comment" in short
    tiny = ga.render_comment(report, PR, limit=300)
    assert len(tiny) <= 300 and tiny.startswith(ga.MARKER) and tiny.endswith("(cut to fit GitHub's comment limit)\n")


def test_saved_example_comment_matches_the_renderer():
    # examples/github-action-comment.md is the dry-run output on tests/fixtures/action/pull_request.json.
    saved = (ROOT / "examples" / "github-action-comment.md").read_text()
    assert saved.startswith(ga.MARKER + "\n")
    assert "Input: example-org/payments-service#42" in saved
    assert "Checked the pull request description." in saved


# ---------------------------------------------------------------- GitHub API


class FakeGitHub:
    def __init__(self, comments):
        self.comments = comments
        self.requests = []

    def transport(self):
        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            assert request.headers["authorization"] == "Bearer t0ken"
            path = request.url.path
            if request.method == "GET" and path.endswith("/issues/7/comments"):
                page = int(request.url.params.get("page", "1"))
                return httpx.Response(200, json=self.comments[(page - 1) * 100 : page * 100])
            if request.method == "POST" and path.endswith("/issues/7/comments"):
                return httpx.Response(201, json={"id": 99, "html_url": "https://github.com/o/r/pull/7#issuecomment-99"})
            m = re.search(r"/issues/comments/(\d+)$", path)
            if request.method == "PATCH" and m:
                return httpx.Response(200, json={"id": int(m.group(1)), "html_url": f"https://github.com/o/r/pull/7#issuecomment-{m.group(1)}"})
            return httpx.Response(404, json={})

        return httpx.MockTransport(handler)


def gh(fake):
    return ga.GitHub("t0ken", "o/r", transport=fake.transport())


def test_publish_creates_then_updates_one_comment():
    fake = FakeGitHub([{"id": 1, "body": "hello", "user": {"login": "alice"}}])
    api = gh(fake)
    assert ga.publish(api, 7, "new body", api.list_comments(7)) == ("created", "https://github.com/o/r/pull/7#issuecomment-99")
    fake.comments.append({"id": 5, "body": f"{ga.MARKER}\nold", "html_url": "h5"})
    assert ga.publish(api, 7, f"{ga.MARKER}\nnew", api.list_comments(7))[0] == "updated"
    assert json.loads(fake.requests[-1].content) == {"body": f"{ga.MARKER}\nnew"}
    assert fake.requests[-1].url.path == "/repos/o/r/issues/comments/5"
    assert ga.publish(api, 7, f"{ga.MARKER}\nold", api.list_comments(7)) == ("unchanged", "h5")
    assert ga.publish(gh(FakeGitHub([])), 7, "x", [], create=False) == ("skipped", None)


def test_list_comments_follows_pages():
    fake = FakeGitHub([{"id": i, "body": str(i)} for i in range(130)])
    assert len(gh(fake).list_comments(7)) == 130
    assert [r.url.params["page"] for r in fake.requests] == ["1", "2"]


# ---------------------------------------------------------------- main, end to end


def run_main(tmp_path, monkeypatch, *, body, extraction, comments, env=None):
    event = {"pull_request": {"number": 7, "title": "Bump requests", "body": body, "html_url": "https://github.com/o/r/pull/7"},
             "repository": {"full_name": "o/r"}}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event))
    out, summary = tmp_path / "out.txt", tmp_path / "summary.md"
    for k, v in {"GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summary), "HEARSAY_GITHUB_TOKEN": "t0ken",
                 "GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "o/r", "GITHUB_RUN_ID": "5", **(env or {})}.items():
        monkeypatch.setenv(k, v)
    fake = FakeGitHub(comments)
    ctx = fixture_context(llm=FakeLLM({"fake-extractor": [json.dumps({"claims": extraction})]}), tavily=False)
    code = ga.main(["--event", str(event_path)], transport=fake.transport(), context=ctx)
    outputs = dict(line.split("=", 1) for line in out.read_text().splitlines())
    return code, outputs, fake, summary.read_text()


def extracted(**c):
    base = {"ecosystem": "pypi", "package": "requests", "version": None, "vulnerability_id": None, "license": None,
            "symbol": None, "parameter": None, "since_version": None, "subject": None, "negated": False, "sentences": [2]}
    return {**base, **c}


def test_main_updates_the_existing_comment_and_sets_outputs(tmp_path, monkeypatch):
    code, outputs, fake, summary = run_main(
        tmp_path, monkeypatch,
        body="Bumped requests to 2.31.0, which fixes CVE-2023-32681.",
        extraction=[extracted(type="fixes_vulnerability", statement="requests 2.31.0 fixes CVE-2023-32681.",
                              version="2.31.0", vulnerability_id="CVE-2023-32681")],
        comments=[{"id": 3, "body": f"{ga.MARKER}\nold report", "html_url": "h3"}],
        env={"HEARSAY_ACTION_FAIL_ON_CONTRADICTED": "true"},
    )
    assert code == 0
    assert outputs == {"claims": "1", "supported": "1", "contradicted": "0", "unverifiable": "0",
                       "comment-url": "https://github.com/o/r/pull/7#issuecomment-3"}
    patch = fake.requests[-1]
    assert patch.method == "PATCH"
    posted = json.loads(patch.content)["body"]
    assert posted.startswith(ga.MARKER) and "Input: o/r#7: Bump requests" in posted
    assert "[Workflow run](https://github.com/o/r/actions/runs/5)" in posted
    assert "**1 claims checked: 1 supported" in summary


def test_main_fails_the_check_on_a_contradiction(tmp_path, monkeypatch, capsys):
    code, outputs, fake, _ = run_main(
        tmp_path, monkeypatch,
        body="The requests library is MIT licensed.",
        extraction=[extracted(type="license_is", statement="requests is MIT licensed.", license="MIT")],
        comments=[],
        env={"HEARSAY_ACTION_FAIL_ON_CONTRADICTED": "true"},
    )
    assert code == 2 and outputs["contradicted"] == "1"
    assert [r.method for r in fake.requests] == ["GET", "POST"]
    assert "::error title=Hearsay::1 claim(s)" in capsys.readouterr().out


def test_main_does_not_post_when_nothing_was_found(tmp_path, monkeypatch):
    code, outputs, fake, _ = run_main(tmp_path, monkeypatch, body="Refactored the retry helper.", extraction=[], comments=[])
    assert code == 0 and outputs["claims"] == "0" and outputs["comment-url"] == ""
    assert [r.method for r in fake.requests] == ["GET"]


def test_main_ignores_comments_from_people_and_from_hearsay(tmp_path, monkeypatch, capsys):
    event = json.loads((EVENTS / "issue_comment.json").read_text())
    event["comment"]["user"] = {"login": "alice", "type": "User"}
    path = tmp_path / "e.json"
    path.write_text(json.dumps(event))
    monkeypatch.setenv("HEARSAY_ACTION_INCLUDE_BOT_COMMENTS", "true")
    assert ga.main(["--event", str(path), "--dry-run"]) == 0
    assert "not from a bot or listed agent" in capsys.readouterr().out


# ---------------------------------------------------------------- action.yml


def test_action_passes_inputs_through_the_environment_only():
    text = (ROOT / "action.yml").read_text()
    run_lines = [l for l in text.splitlines() if l.strip().startswith("run:")]
    assert run_lines and all("${{" not in l for l in run_lines)
    inputs = re.findall(r"^  ([a-z-]+):\n    description:", text.split("\noutputs:")[0], re.M)
    assert set(inputs) >= {"tavily-api-key", "llm-api-key", "llm-base-url", "fail-on-contradicted", "include-bot-comments"}
    for name in inputs:
        assert f"inputs.{name}" in text, name
    # Third-party actions are pinned to a commit.
    for ref in re.findall(r"uses: (\S+)", text):
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", ref), ref
