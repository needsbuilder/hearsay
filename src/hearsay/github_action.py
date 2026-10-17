"""The script behind the GitHub Action (action.yml): check a pull request and
post or update one comment with the report.

In a workflow it reads the event from GITHUB_EVENT_PATH and its options from
HEARSAY_ACTION_* variables that action.yml sets from the inputs. Locally:

    python -m hearsay.github_action --event saved-event.json --dry-run --comment-out comment.md

What is checked: the pull request title and description, and, with
include-bot-comments, the comments on the pull request written by bot accounts
or by the logins listed in agent-logins. Hearsay's own comment is never checked.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from .config import Settings
from .models import Report
from .pipeline import Context, check
from .report import to_markdown

MARKER = "<!-- hearsay-report -->"
GITHUB_COMMENT_LIMIT = 65_536
MAX_COMMENT_CHARS = 60_000  # leaves room for the header and footer


@dataclass
class PullRequest:
    repo: str
    number: int
    title: str
    body: str
    url: str


@dataclass
class AgentComment:
    author: str
    body: str
    url: str


@dataclass
class Options:
    fail_on_contradicted: bool = False
    include_bot_comments: bool = False
    agent_logins: set[str] = field(default_factory=set)
    comment_on_empty: bool = False

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Options":
        env = dict(os.environ if env is None else env)

        def flag(name: str) -> bool:
            return env.get(name, "").strip().lower() in ("1", "true", "yes", "on")

        logins = {x.strip().lower() for x in env.get("HEARSAY_ACTION_AGENT_LOGINS", "").split(",") if x.strip()}
        return cls(
            fail_on_contradicted=flag("HEARSAY_ACTION_FAIL_ON_CONTRADICTED"),
            include_bot_comments=flag("HEARSAY_ACTION_INCLUDE_BOT_COMMENTS"),
            agent_logins=logins,
            comment_on_empty=flag("HEARSAY_ACTION_COMMENT_ON_EMPTY"),
        )


# ------------------------------------------------------------------ event


def pull_request_from_event(event: dict[str, Any], repo: str | None = None) -> PullRequest | None:
    """The pull request a `pull_request`, `pull_request_target` or `issue_comment` event is about."""
    repo = repo or (event.get("repository") or {}).get("full_name") or ""
    pr = event.get("pull_request")
    if isinstance(pr, dict):
        return PullRequest(repo, int(pr["number"]), pr.get("title") or "", pr.get("body") or "", pr.get("html_url") or "")
    issue = event.get("issue")
    if isinstance(issue, dict) and issue.get("pull_request"):
        return PullRequest(
            repo, int(issue["number"]), issue.get("title") or "", issue.get("body") or "", issue.get("html_url") or ""
        )
    return None


def is_agent(user: dict[str, Any] | None, agent_logins: set[str]) -> bool:
    """A bot account (GitHub Apps, Dependabot, Copilot, Devin...) or a login listed as an agent."""
    if not user:
        return False
    login = (user.get("login") or "").lower()
    return user.get("type") == "Bot" or login in agent_logins or login.removesuffix("[bot]") in agent_logins


def agent_comments(comments: list[dict[str, Any]], agent_logins: set[str]) -> list[AgentComment]:
    out = []
    for c in comments:
        body = c.get("body") or ""
        if MARKER in body or not body.strip():
            continue
        if is_agent(c.get("user"), agent_logins):
            out.append(AgentComment((c.get("user") or {}).get("login") or "?", body, c.get("html_url") or ""))
    return out


def build_input(pr: PullRequest, comments: list[AgentComment]) -> str:
    parts = [f"{pr.title}\n\n{pr.body}".strip()]
    for c in comments:
        parts.append(f"Comment by @{c.author}:\n\n{c.body.strip()}")
    return "\n\n---\n\n".join(parts)


# ------------------------------------------------------------------ comment


def render_comment(
    report: Report,
    pr: PullRequest,
    *,
    comments: list[AgentComment] | None = None,
    notes: list[str] | None = None,
    run_url: str | None = None,
    limit: int = MAX_COMMENT_CHARS,
) -> str:
    """The comment body: a hidden marker (to find it again), the Markdown report and a footer."""
    comments = comments or []
    scope = "the pull request description"
    if comments:
        authors = ", ".join(sorted({f"@{c.author}" for c in comments}))
        scope += f" and {len(comments)} comment{'s' if len(comments) != 1 else ''} by {authors}"
    footer = [f"Checked {scope}."]
    footer += list(notes or [])
    if run_url:
        footer.append(f"[Workflow run]({run_url})")
    tail = "\n" + "\n\n".join(footer) + "\n"

    head = f"{MARKER}\n"
    body = to_markdown(report)
    if len(head) + len(body) + len(tail) > limit:
        body = _summary_only(report)
        tail = "\n" + "\n\n".join(
            footer[:1]
            + ["The details per claim did not fit in one comment; they are in the job summary of the workflow run."]
            + footer[1:]
        ) + "\n"
    text = f"{head}{body}{tail}"
    if len(text) > limit:  # a very long claim list: cut the table itself
        text = text[: limit - 80].rsplit("\n", 1)[0] + "\n\n(cut to fit GitHub's comment limit)\n"
    return text


def _summary_only(report: Report) -> str:
    full = to_markdown(report)
    head, _, _ = full.partition("\n### ")  # the totals and the table come before the first claim heading
    return head.rstrip() + "\n"


# ------------------------------------------------------------------ GitHub API


class GitHub:
    def __init__(self, token: str, repo: str, api_url: str = "https://api.github.com", transport: httpx.BaseTransport | None = None):
        self.repo = repo
        self.client = httpx.Client(
            base_url=api_url.rstrip("/"),
            transport=transport,
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "hearsay-action",
            },
        )

    def list_comments(self, number: int) -> list[dict[str, Any]]:
        comments: list[dict[str, Any]] = []
        page = 1
        while True:
            res = self.client.get(f"/repos/{self.repo}/issues/{number}/comments", params={"per_page": 100, "page": page})
            res.raise_for_status()
            batch = res.json()
            comments.extend(batch)
            if len(batch) < 100:
                return comments
            page += 1

    def create_comment(self, number: int, body: str) -> dict[str, Any]:
        res = self.client.post(f"/repos/{self.repo}/issues/{number}/comments", json={"body": body})
        res.raise_for_status()
        return res.json()

    def update_comment(self, comment_id: int, body: str) -> dict[str, Any]:
        res = self.client.patch(f"/repos/{self.repo}/issues/comments/{comment_id}", json={"body": body})
        res.raise_for_status()
        return res.json()

    def close(self) -> None:
        self.client.close()


def find_report_comment(comments: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((c for c in comments if MARKER in (c.get("body") or "")), None)


def publish(gh: GitHub, number: int, body: str, comments: list[dict[str, Any]], *, create: bool = True) -> tuple[str, str | None]:
    """Update Hearsay's comment if there is one, else create it. Returns (action, comment URL)."""
    existing = find_report_comment(comments)
    if existing is not None:
        if (existing.get("body") or "") == body:
            return "unchanged", existing.get("html_url")
        return "updated", gh.update_comment(int(existing["id"]), body).get("html_url")
    if not create:
        return "skipped", None
    return "created", gh.create_comment(number, body).get("html_url")


# ------------------------------------------------------------------ main


def _write_github_file(var: str, text: str) -> None:
    path = os.environ.get(var)
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text)


def _set_outputs(values: dict[str, Any]) -> None:
    _write_github_file("GITHUB_OUTPUT", "".join(f"{k}={v}\n" for k, v in values.items()))


def run_url_from_env() -> str | None:
    server, repo, run_id = (os.environ.get(k) for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    return f"{server}/{repo}/actions/runs/{run_id}" if server and repo and run_id else None


def main(argv: list[str] | None = None, *, transport: httpx.BaseTransport | None = None, context: Context | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hearsay.github_action", description=__doc__.splitlines()[0])
    parser.add_argument("--event", default=os.environ.get("GITHUB_EVENT_PATH"), help="event JSON (default $GITHUB_EVENT_PATH)")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY"), help="OWNER/REPO (default $GITHUB_REPOSITORY)")
    parser.add_argument("--dry-run", action="store_true", help="do not call the GitHub API; print the comment")
    parser.add_argument("--comment-out", metavar="PATH", help="also write the comment body to PATH")
    parser.add_argument("--json-out", metavar="PATH", help="also write the JSON report to PATH")
    args = parser.parse_args(argv)
    opts = Options.from_env()

    if not args.event:
        print("hearsay: no event file (GITHUB_EVENT_PATH); nothing to check", file=sys.stderr)
        return 1
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    pr = pull_request_from_event(event, args.repo)
    if pr is None:
        print("hearsay: the event is not about a pull request; nothing to do")
        return 0
    trigger = event.get("comment")
    if isinstance(trigger, dict):
        # issue_comment: only an agent's new comment is a reason to check again, and never Hearsay's own.
        if MARKER in (trigger.get("body") or "") or not (opts.include_bot_comments and is_agent(trigger.get("user"), opts.agent_logins)):
            print("hearsay: the comment is not from a bot or listed agent; nothing to do")
            return 0

    gh = None
    existing: list[dict[str, Any]] = []
    if not args.dry_run:
        token = os.environ.get("HEARSAY_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            print("hearsay: no GitHub token (input github-token)", file=sys.stderr)
            return 1
        gh = GitHub(token, pr.repo, os.environ.get("GITHUB_API_URL", "https://api.github.com"), transport=transport)
        existing = gh.list_comments(pr.number)
    included = agent_comments(existing, opts.agent_logins) if opts.include_bot_comments else []
    if opts.include_bot_comments and args.dry_run and isinstance(trigger, dict):
        included = agent_comments([trigger], opts.agent_logins)

    notes: list[str] = []
    if context is None:
        settings = Settings.from_env()
        problems = settings.llm_problems()
        if problems:
            notes.append(
                "Model settings are missing, so claims were found by patterns only (install commands, version pins, "
                "\"fixes CVE-...\" sentences, licence phrases, npm deprecations) and documentation claims were not checked."
            )
        context = Context.create(settings, use_llm=not problems)
    try:
        report = check(build_input(pr, included), context=context)
    finally:
        context.close()
    report.input_title = f"{pr.repo}#{pr.number}: {pr.title}"
    report.input_url = pr.url or None

    body = render_comment(report, pr, comments=included, notes=notes, run_url=run_url_from_env())
    _write_github_file("GITHUB_STEP_SUMMARY", to_markdown(report, include_evidence=False) + "\n")
    if args.json_out:
        Path(args.json_out).write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
    if args.comment_out:
        Path(args.comment_out).write_text(body, encoding="utf-8")

    t = report.totals
    comment_url = None
    if args.dry_run:
        print(body)
        action = "dry-run"
    else:
        assert gh is not None
        try:
            action, comment_url = publish(gh, pr.number, body, existing, create=bool(t.claims) or opts.comment_on_empty)
        finally:
            gh.close()
        print(f"hearsay: comment {action}{f': {comment_url}' if comment_url else ''}")
    _set_outputs(
        {
            "claims": t.claims,
            "supported": t.supported,
            "contradicted": t.contradicted,
            "unverifiable": t.unverifiable,
            "comment-url": comment_url or "",
        }
    )
    print(f"hearsay: {t.claims} claims, {t.supported} supported, {t.contradicted} contradicted, {t.unverifiable} unverifiable")
    if opts.fail_on_contradicted and t.contradicted:
        print(f"::error title=Hearsay::{t.contradicted} claim(s) in this pull request are contradicted by a primary source.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
