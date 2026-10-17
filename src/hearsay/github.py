"""Read a pull request description through the public GitHub REST API."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .http import Http

_SPEC = re.compile(r"^(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)#(?P<number>\d+)$")
_URL = re.compile(r"^https?://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/pull/(?P<number>\d+)")


@dataclass
class PullRequest:
    owner: str
    repo: str
    number: int
    title: str
    body: str
    url: str


def parse_pr_spec(spec: str) -> tuple[str, str, int]:
    s = spec.strip()
    m = _SPEC.match(s) or _URL.match(s)
    if not m:
        raise ValueError(f"expected OWNER/REPO#NUMBER or a pull request URL, got {spec!r}")
    return m.group("owner"), m.group("repo"), int(m.group("number"))


def fetch_pull_request(http: Http, spec: str) -> PullRequest:
    owner, repo, number = parse_pr_spec(spec)
    api = f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}"
    res = http.get(api, headers={"Accept": "application/vnd.github+json"})
    if res.status != 200 or not isinstance(res.data, dict):
        raise ValueError(f"GitHub returned HTTP {res.status} for {owner}/{repo}#{number}")
    return PullRequest(
        owner=owner,
        repo=repo,
        number=number,
        title=res.data.get("title") or "",
        body=res.data.get("body") or "",
        url=res.data.get("html_url") or f"https://github.com/{owner}/{repo}/pull/{number}",
    )
