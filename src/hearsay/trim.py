"""Keep only the third-party text a run used, in committed fixtures and the demo bundle.

Fixtures and the web demo bundle replay real runs from cached answers. A
cached Tavily Extract answer holds whole documentation pages and a Search
answer holds snippets. Third-party documentation is not ours to republish
(Stripe's docs, for one, are not openly licensed), so before anything is
committed these answers are cut down to:

- the windows the run showed the judges, each re-emitted under its original
  heading lines, so the page parses to the same windows with the same
  heading paths; plus any windows a caller asks to keep (tests that look at
  a specific section);
- a one-line heading for a page none of whose windows was used, so the code
  still treats the extract as successful;
- search snippets only where the run used one as a page (its extract
  failed); URLs, titles and scores are kept, because they decide which
  pages are read.

Why replay stays exact: passage selection scores each window on its own
text, heading path and API heading. If every chosen window survives
unchanged and in the same order, and nothing new appears, the same windows
are chosen, so the judge prompts (and their cache keys) are identical. Each
trimmed page is checked by parsing it again; callers also replay the whole
run and compare the reports.

Registry, OSV, deps.dev and GitHub JSON is data, not prose; trim_registry()
only drops the fields Hearsay never reads, to keep files small.
"""

from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from .models import Passage, Report
from .passages import Window, page_windows

# A committed page may hold at most this many characters (tests enforce it).
MAX_PAGE_CHARS = 20_000

PLACEHOLDER = "# (page text not kept: no passage from this page was used)"

WindowKey = tuple[str, tuple[str, ...], str | None, str]
KeepExtra = Callable[[str, Window], bool]


class TrimError(RuntimeError):
    pass


def _url(url: str) -> str:
    return url.strip().rstrip("/")


def window_key(url: str, section: Iterable[str], api_heading: str | None, text: str) -> WindowKey:
    return (_url(url), tuple(section), api_heading, text)


def used_windows(passages: Iterable[Passage]) -> set[WindowKey]:
    return {window_key(p.url, p.section, p.api_heading, p.text) for p in passages}


def used_in_reports(reports: Iterable[Report]) -> set[WindowKey]:
    return used_windows(p for report in reports for r in report.results for p in r.evidence)


# ------------------------------------------------------------------ pages


def _indent_for(w: Window) -> str:
    # Re-emitted text must stay inside a Sphinx definition's body, which is
    # the lines indented under the definition term.
    inner = w.headings[-1] if w.headings else None
    return " " * ((inner.indent if inner and inner.level >= 7 else 0) + 4)


def _block(w: Window, text: str) -> str:
    """The window's heading lines, then its text with every paragraph's first line indented.

    Indenting is safe: the parser strips it again, and an indented line is
    never read as a heading.
    """
    prefix = _indent_for(w)
    body = "\n\n".join(prefix + para for para in text.split("\n\n"))
    return "\n".join(h.raw for h in w.headings) + "\n\n" + body


def _emit_windows(windows: list[Window]) -> str:
    return "\n\n".join(_block(w, w.text) for w in windows)


def _emit_sections(windows: list[Window]) -> str:
    """Fallback: whole sections (heading lines and full body) for the kept windows."""
    seen: set[int] = set()
    blocks = []
    for w in windows:
        if id(w.body) in seen:
            continue
        seen.add(id(w.body))
        blocks.append(_block(w, w.body))
    return "\n\n".join(blocks)


def _keys(url: str, windows: list[Window]) -> list[WindowKey]:
    return [window_key(url, w.section, w.api_heading, w.text) for w in windows]


def _is_subsequence(small: list, big: list) -> bool:
    it = iter(big)
    return all(any(x == y for y in it) for x in small)


def trim_page(url: str, text: str, used: set[WindowKey], keep_extra: KeepExtra | None = None) -> str:
    """The page cut down to its used (and extra) windows. Raises TrimError if that
    cannot be done without changing how the page parses."""
    original = page_windows(url, "", text)
    keep = [w for w in original if window_key(url, w.section, w.api_heading, w.text) in used or (keep_extra and keep_extra(url, w))]
    if not keep:
        return PLACEHOLDER
    original_keys = _keys(url, original)
    wanted = set(_keys(url, keep))
    for emit in (_emit_windows, _emit_sections):
        trimmed = emit(keep)
        again = _keys(url, page_windows(url, "", trimmed))
        if wanted <= set(again) and _is_subsequence(again, original_keys):
            return trimmed
    raise TrimError(f"cannot trim {url} without changing how it parses")


def _is_extract(request: dict | None, data: dict) -> bool:
    if request and request.get("url"):
        return str(request["url"]).endswith("/extract")
    return "query" not in data  # Search answers echo the query; Extract answers (without one) do not


def trim_tavily(
    entries: dict[str, Any],
    used: set[WindowKey],
    keep_extra: KeepExtra | None = None,
    requests: dict[str, dict] | None = None,
) -> dict[str, Any]:
    """Trim every cached Tavily answer in {key: response}. Returns a new dict.

    `requests` ({key: request}) tells Search and Extract answers apart; without
    it the answer's own fields are used.
    """
    requests = requests or {}
    kinds = {}
    requested: set[str] = set()
    extracted: set[str] = set()
    for key, response in entries.items():
        data = (response or {}).get("data")
        if not isinstance(data, dict):
            continue
        kinds[key] = "extract" if _is_extract(requests.get(key), data) else "search"
        if kinds[key] != "extract":
            continue
        for r in data.get("results") or []:
            requested.add(_url(r.get("url", "")))
            if r.get("raw_content"):
                extracted.add(_url(r.get("url", "")))
        for f in data.get("failed_results") or []:
            requested.add(_url(f.get("url", "")))

    out = {}
    for key, response in entries.items():
        data = (response or {}).get("data")
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            out[key] = response
            continue
        results = []
        for r in data["results"]:
            url = r.get("url", "")
            if kinds.get(key) == "extract":  # a whole page
                page = r.get("raw_content") or ""
                results.append({"url": url, "raw_content": trim_page(url, page, used, keep_extra) if page else ""})
            else:  # a Search hit: keep its snippet only if it stood in for a failed extract
                snippet = r.get("content") or ""
                keep_snippet = _url(url) in requested and _url(url) not in extracted
                results.append(
                    {"url": url, "title": r.get("title") or "", "score": r.get("score"), "content": snippet if keep_snippet else ""}
                )
        new_data = {"results": results}
        if data.get("failed_results"):
            new_data["failed_results"] = [{"url": f.get("url", "")} for f in data["failed_results"]]
        out[key] = {**{k: v for k, v in response.items() if k != "data"}, "data": new_data, "trimmed": True}
    return out


# ------------------------------------------------------------------ registry JSON

INFO_KEYS = ("name", "version", "license", "license_expression", "classifiers", "home_page", "docs_url", "project_urls")
_OSV_KEYS = ("id", "aliases", "published", "modified", "summary", "affected")


def _osv_record(v: dict) -> dict:
    r = {k: v[k] for k in _OSV_KEYS if k in v}
    nvd = (v.get("database_specific") or {}).get("nvd_published_at")
    if nvd:
        r["database_specific"] = {"nvd_published_at": nvd}
    return r


def trim_registry(request: dict, response: Any) -> Any:
    """Drop the fields of registry, OSV, deps.dev and GitHub answers that Hearsay never reads."""
    if not isinstance(response, dict) or response.get("status") != 200:
        return response
    url, data = request.get("url", ""), response.get("data")
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
        if "vulns" in data:
            out = {"vulns": [_osv_record(v) for v in data["vulns"]]}
            if data.get("next_page_token"):
                out["next_page_token"] = data["next_page_token"]
        else:
            out = _osv_record(data)
    elif url.startswith("https://api.github.com/repos/"):
        out = {k: data.get(k) for k in ("number", "title", "body", "html_url")}
    elif url.startswith("https://api.deps.dev/"):
        out = {k: data[k] for k in ("versionKey", "licenses", "links") if k in data}
    if out is None:
        return response
    return {"status": 200, "data": out, "trimmed": True}


def page_text_sizes(obj: Any) -> Iterable[tuple[int, str]]:
    """(length, url) for every page text or snippet in a cached Tavily answer (or any JSON)."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("raw_content", "content") and isinstance(v, str):
                yield len(v), str(obj.get("url", ""))
            else:
                yield from page_text_sizes(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from page_text_sizes(v)
