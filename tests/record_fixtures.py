"""Record the real responses the test suite replays (tests/fixtures/cache).

    uv run python tests/record_fixtures.py [--dev-cache .hearsay-cache]

- PyPI, npm, deps.dev, OSV and GitHub answers come from the development
  cache when present, otherwise they are fetched live.
- Tavily answers are only ever copied from the development cache, which
  real `hearsay check` runs filled. Network access to Tavily is blocked
  here, so recording never spends Tavily credits.
- Large registry responses are trimmed to the fields Hearsay reads, and
  extracted pages over 1 MB (Node's single-page all.html) are emptied; the
  stored entry is marked "trimmed": true.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))

from support import DOCS_CLAIMS, FIXTURE_CACHE, FakeLLM, claim, docs_claim  # noqa: E402

from hearsay.cache import Cache  # noqa: E402
from hearsay.config import Settings  # noqa: E402
from hearsay.docs import check_docs_claim  # noqa: E402
from hearsay.github import fetch_pull_request  # noqa: E402
from hearsay.http import Http  # noqa: E402
from hearsay.models import Usage  # noqa: E402
from hearsay.pipeline import Context, check_claim  # noqa: E402
from hearsay.tavily import TavilyClient  # noqa: E402

INFO_KEYS = ("name", "version", "license", "license_expression", "classifiers", "home_page", "docs_url", "project_urls")


MAX_PAGE_CHARS = 1_000_000


def trim(namespace: str, request: dict, response: dict) -> dict:
    if namespace == "tavily" and request["url"].endswith("/extract") and isinstance(response, dict):
        results = (response.get("data") or {}).get("results") or []
        if any(len(r.get("raw_content") or "") > MAX_PAGE_CHARS for r in results):
            data = dict(response["data"])
            data["results"] = [
                {**r, "raw_content": ""} if len(r.get("raw_content") or "") > MAX_PAGE_CHARS else r for r in results
            ]
            return {"status": response["status"], "data": data, "trimmed": True}
        return response
    if namespace != "http" or not isinstance(response, dict) or response.get("status") != 200:
        return response
    url, data = request["url"], response["data"]
    if not isinstance(data, dict):
        return response
    out = None
    if re.fullmatch(r"https://pypi\.org/pypi/[^/]+/json", url):
        releases = {}
        for ver, files in (data.get("releases") or {}).items():
            releases[ver] = (
                [{"yanked": all(f.get("yanked") for f in files), "yanked_reason": files[0].get("yanked_reason")}]
                if files
                else []
            )
        out = {"info": {k: data["info"].get(k) for k in INFO_KEYS}, "releases": releases}
    elif re.fullmatch(r"https://pypi\.org/pypi/[^/]+/[^/]+/json", url):
        out = {"info": {k: data["info"].get(k) for k in INFO_KEYS}}
    elif url.startswith("https://registry.npmjs.org/") and (request.get("headers") or {}).get("Accept", "").startswith(
        "application/vnd.npm.install-v1"
    ):
        out = {
            "name": data.get("name"),
            "dist-tags": data.get("dist-tags"),
            "versions": {
                v: {k: m[k] for k in ("name", "version", "deprecated") if k in m}
                for v, m in (data.get("versions") or {}).items()
            },
        }
    elif url.startswith("https://registry.npmjs.org/"):
        out = {k: data[k] for k in ("name", "version", "license", "licenses", "homepage", "repository", "deprecated") if k in data}
    elif url.startswith("https://api.osv.dev/"):
        keep = ("id", "aliases", "published", "modified", "summary", "affected")
        if "vulns" in data:
            out = {"vulns": [{k: v[k] for k in keep if k in v} for v in data["vulns"]]}
            if data.get("next_page_token"):
                out["next_page_token"] = data["next_page_token"]
        else:
            out = {k: data[k] for k in keep if k in data}
    elif url.startswith("https://api.github.com/repos/"):
        out = {k: data.get(k) for k in ("number", "title", "body", "html_url")}
    elif url.startswith("https://api.deps.dev/"):
        out = {k: data[k] for k in ("versionKey", "licenses", "links") if k in data}
    if out is None:
        return response
    return {"status": 200, "data": out, "trimmed": True}


class RecordingCache(Cache):
    def __init__(self, fixture_root: Path, dev_root: Path):
        super().__init__(fixture_root)
        self.fixture = Cache(fixture_root)
        self.dev = Cache(dev_root)
        self.missing_tavily: list[dict] = []

    def get(self, namespace, request):
        value = self.fixture.get(namespace, request)
        if not Cache.is_missing(value):
            return value
        value = self.dev.get(namespace, request)
        if Cache.is_missing(value):
            if namespace == "tavily":
                self.missing_tavily.append(request)
            return value
        trimmed = trim(namespace, request, value)
        self.fixture.put(namespace, request, trimmed)
        return trimmed

    def put(self, namespace, request, response):
        self.fixture.put(namespace, request, trim(namespace, request, response))


def block_tavily() -> httpx.BaseTransport:
    real = httpx.HTTPTransport(retries=1)

    class Guard(httpx.BaseTransport):
        def handle_request(self, request: httpx.Request) -> httpx.Response:
            if request.url.host == "api.tavily.com":
                raise httpx.ConnectError("Tavily is blocked while recording fixtures")
            return real.handle_request(request)

    return Guard()


RECORD = [
    claim("fixes_vulnerability", package="requests", version="2.31.0", vulnerability_id="CVE-2023-32681", ecosystem="pypi"),
    claim("fixes_vulnerability", package="requests", version="2.0.0", vulnerability_id="CVE-2023-32681", ecosystem="pypi"),
    claim("affected_by_vulnerability", package="requests", version="2.30.0", vulnerability_id="CVE-2023-32681", ecosystem="pypi"),
    claim("affected_by_vulnerability", package="requests", version="2.31.0", ecosystem="pypi"),
    claim("affected_by_vulnerability", package="requests", version="2.33.0", ecosystem="pypi", negated=True),
    claim("fixes_vulnerability", package="requests", version="2.31.0", vulnerability_id="CVE-2099-0001", ecosystem="pypi"),
    claim("fixes_vulnerability", package="urllib3", version="1.26.5", vulnerability_id="CVE-2023-43804", ecosystem="pypi"),
    claim("fixes_vulnerability", package="urllib3", version="1.26.18", vulnerability_id="CVE-2023-32681", ecosystem="pypi"),
    claim("affected_by_vulnerability", package="lodash", version="4.17.21", vulnerability_id="CVE-2021-23337", ecosystem="npm"),
    claim("affected_by_vulnerability", package="lodash", version="4.17.20", vulnerability_id="CVE-2021-23337", ecosystem="npm"),
    claim("package_exists", package="requests", ecosystem="pypi"),
    claim("package_exists", package="pydantic-settings-extra"),
    claim("package_exists", package="left-pad-hearsay-nonexistent", ecosystem="npm"),
    claim("version_exists", package="requests", version="2.31", ecosystem="pypi"),
    claim("version_exists", package="requests", version="2.32.0", ecosystem="pypi"),
    claim("version_exists", package="requests", version="2.99.0", ecosystem="pypi"),
    claim("version_exists", package="fastapi", version="0.200.0", ecosystem="pypi"),
    claim("version_exists", package="express", version="4.21.2", ecosystem="npm"),
    claim("version_exists", package="express", version="9.9.9", ecosystem="npm"),
    claim("license_is", package="requests", license="MIT", ecosystem="pypi"),
    claim("license_is", package="requests", license="Apache 2.0", ecosystem="pypi"),
    claim("license_is", package="requests", license="MIT"),
    claim("license_is", package="httpx", license="BSD-3-Clause", ecosystem="pypi"),
    claim("license_is", package="httpx", license="BSD", ecosystem="pypi"),
    claim("license_is", package="express", version="5.0.0", license="MIT", ecosystem="npm"),
    claim("deprecated", package="left-pad", ecosystem="npm"),
    claim("deprecated", package="express", ecosystem="npm"),
]

GITHUB_PRS = ["gesiscss/gesis_surf_backend#67"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-cache", default=".hearsay-cache")
    args = ap.parse_args()

    cache = RecordingCache(FIXTURE_CACHE, Path(args.dev_cache))
    usage = Usage()
    http = Http(cache, usage, transport=block_tavily())
    settings = Settings(
        llm_api_key="unused", extract_model="x", judge_models=["judge-a"], adjudicator_model="judge-b",
        tavily_api_key="unused", cache_dir=None,
    )
    tavily = TavilyClient(http, "unused", max_calls=0)  # any real Tavily call would exceed the budget
    unverifiable = '{"reasoning": "-", "verdict": "unverifiable", "url": null, "quote": ""}'
    ctx = Context(settings, usage, cache, http, tavily, FakeLLM(lambda m, msgs: unverifiable))

    for c in RECORD:
        r = check_claim(ctx, c)
        print(f"{r.verdict.value:13} {c.type.value:26} {c.package} {c.version or ''} {c.vulnerability_id or ''} {c.license or ''}")
    for name in DOCS_CLAIMS:
        r = check_docs_claim(ctx, docs_claim(name))
        print(f"{r.verdict.value:13} docs:{name} passages={len(r.evidence)} {r.reason[:80]}")
    for spec in GITHUB_PRS:
        pr = fetch_pull_request(http, spec)
        print(f"github       {spec}: {pr.title[:60]} ({len(pr.body)} chars)")
    if cache.missing_tavily:
        print(f"\n{len(cache.missing_tavily)} Tavily responses missing from the dev cache (not recorded):")
        for req in cache.missing_tavily:
            print("  ", req.get("url"), str(req.get("json"))[:120])
    print(f"\nlive HTTP requests: {usage.http_requests}; Tavily network calls: {usage.tavily_calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
