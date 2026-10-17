"""Which search results are the same page, and which are an old version of the docs.

Tavily can return one page under several URLs (an anchor, a trailing slash,
a `?lang=` variant, `/en/latest/` and `/en/master/`), and versioned docs
under several versions (`docs.python.org/2.7/`, `/3.4/`, `/3/`). Before the
three Extract slots are filled, results are ordered (current docs first,
unless the claim names a version) and duplicates are dropped.
"""

from __future__ import annotations

import re
from typing import Protocol, TypeVar
from urllib.parse import parse_qsl, urlencode, urlsplit

# A locale as the first path segment: /en-US/docs/..., /ja/3/library/...
LOCALES = {
    "en", "en-us", "en-gb", "de", "es", "fr", "it", "ja", "ko", "pl", "pt", "pt-br", "ru", "tr", "uk", "id",
    "zh", "zh-cn", "zh-tw", "zh_cn", "zh_tw",
}
# Query parameters that select a variant of the same page.
VARIANT_PARAMS = {"lang", "language", "locale", "hl", "api-version", "__"}
# Path segments that mean "the current docs" on versioned sites.
CURRENT_MARKERS = {"latest", "stable", "current", "main", "master", "dev"}

# A version segment: 2.7, 3.12, v8.0.0, 18.x, latest-v18.x, v18.x. A bare
# integer ("3" on docs.python.org, "v1" in an API path) is not one.
_VERSION = re.compile(r"^(?:latest-)?v?(\d+(?:\.\d+)+)(?:\.x)?$|^(?:latest-)?v?(\d+)\.x$")


def _segments(url: str) -> list[str]:
    segs = [s for s in urlsplit(url).path.split("/") if s]
    if segs and segs[0].lower() in LOCALES:
        segs = segs[1:]
    return segs


def doc_version(url: str) -> str | None:
    """The documentation version a URL is for, or None for the current docs."""
    for seg in _segments(url):
        m = _VERSION.match(seg.lower())
        if m:
            return m.group(1) or m.group(2)
    return None


def page_key(url: str) -> str:
    """URLs with the same key are the same page."""
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    segs = ["{current}" if s.lower() in CURRENT_MARKERS else s for s in _segments(url)]
    if segs and segs[-1].lower() in ("index.html", "index.htm"):
        segs.pop()
    if segs:
        segs[-1] = re.sub(r"\.html?$", "", segs[-1])
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if k.lower() not in VARIANT_PARAMS and not k.lower().startswith("utm_")
    )
    return host + "/" + "/".join(segs) + ("?" + urlencode(query) if query else "")


def version_matches(page_version: str, claimed: str) -> bool:
    page, want = page_version.lstrip("vV"), claimed.strip().lstrip("vV")
    return page == want or want.startswith(page + ".") or page.startswith(want + ".")


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(-int(x) for x in re.findall(r"\d+", version))  # newest first


class HasUrl(Protocol):
    url: str


T = TypeVar("T", bound=HasUrl)


def order_and_dedupe(hits: list[T], claimed_version: str | None = None) -> list[T]:
    """Current docs first (or pages for the claimed version first), newer versions
    before older ones, search order otherwise; then one URL per page."""

    def rank(item: tuple[int, T]) -> tuple:
        index, hit = item
        version = doc_version(hit.url)
        if claimed_version and version and version_matches(version, claimed_version):
            group = 0
        elif version is None:
            group = 1 if claimed_version else 0
        else:
            group = 2
        return (group, _version_key(version) if group == 2 and version else (), index)

    ordered = [hit for _, hit in sorted(enumerate(hits), key=rank)]
    seen: set[str] = set()
    out = []
    for hit in ordered:
        key = page_key(hit.url)
        if key not in seen:
            seen.add(key)
            out.append(hit)
    return out


def only_old_versions_note(urls: list[str], claimed_version: str | None = None) -> str | None:
    """A report note when every page used is for a specific, non-claimed version."""
    versions = [doc_version(u) for u in urls]
    if not urls or any(v is None for v in versions):
        return None
    if claimed_version and all(v and version_matches(v, claimed_version) for v in versions):
        return None
    listed = ", ".join(sorted({v for v in versions if v}, key=_version_key))
    return (
        f"Only version-specific documentation pages came back (versions {listed}); "
        "none of them is the current documentation, so the verdict may describe an old release."
    )
