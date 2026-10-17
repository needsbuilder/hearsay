"""What is committed keeps only the documentation passages Hearsay used.

Fixtures and the web demo bundle replay real runs from cached answers, and a
cached Tavily Extract answer is a whole third-party page. Those pages are not
ours to republish (Stripe's documentation is not openly licensed), so the
recorder and the bundle builder trim them (src/hearsay/trim.py). These tests
fail if a committed file holds more page text than that.
"""

import gzip
import json
from pathlib import Path

from hearsay.passages import page_windows
from hearsay.trim import MAX_PAGE_CHARS, PLACEHOLDER, page_text_sizes, trim_page, trim_tavily, window_key

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "src" / "hearsay" / "web" / "demo" / "bundle.json.gz"


def committed_json():
    for f in sorted((ROOT / "tests" / "fixtures").rglob("*.json")):
        yield f.relative_to(ROOT), json.loads(f.read_text(encoding="utf-8"))
    with gzip.open(BUNDLE, "rt", encoding="utf-8") as fh:
        yield BUNDLE.relative_to(ROOT), json.load(fh)
    for f in sorted((ROOT / "examples").glob("*.json")):
        yield f.relative_to(ROOT), json.loads(f.read_text(encoding="utf-8"))
    for f in sorted((ROOT / "bench" / "results").rglob("*.json*")):
        lines = f.read_text(encoding="utf-8").splitlines() if f.suffix == ".jsonl" else [f.read_text(encoding="utf-8")]
        for line in lines:
            if line.strip():
                yield f.relative_to(ROOT), json.loads(line)


def test_no_committed_page_holds_more_than_the_limit():
    too_big = [
        (str(path), url, n)
        for path, data in committed_json()
        for n, url in page_text_sizes(data)
        if n > MAX_PAGE_CHARS
    ]
    assert not too_big, f"pages over {MAX_PAGE_CHARS} characters: {too_big[:5]}"


def test_committed_tavily_answers_are_trimmed():
    fixtures = list((ROOT / "tests" / "fixtures" / "cache" / "tavily").rglob("*.json"))
    assert fixtures
    for f in fixtures:
        assert json.loads(f.read_text(encoding="utf-8"))["response"].get("trimmed") is True, f
    with gzip.open(BUNDLE, "rt", encoding="utf-8") as fh:
        tavily = json.load(fh)["cache"].get("tavily", {})
    assert tavily and all(r.get("trimmed") is True for r in tavily.values())


SPHINX_PAGE = """# `datetime` Objects[\u00b6](#datetime-objects "Link to this heading")

Intro text about datetime objects, long enough to be a window.

*classmethod* datetime.now(*tz=None*)[\u00b6](#datetime.datetime.now "Link to this definition")
:   Return the current local date and time.

    This function is preferred over [`utcnow()`](#datetime.datetime.utcnow "datetime.datetime.utcnow").

*classmethod* datetime.utcnow()[\u00b6](#datetime.datetime.utcnow "Link to this definition")
:   Return the current UTC date and time, with tzinfo None.

    Warning: naive datetime objects are treated by many methods as local times.

    Deprecated since version 3.12: Use `datetime.now()` with `UTC` instead.

## Other section[\u00b6](#other "Link to this heading")

An unrelated paragraph that nobody used for anything at all.
"""
URL = "https://docs.python.org/3/library/datetime.html"


def keys(text):
    return [window_key(URL, w.section, w.api_heading, w.text) for w in page_windows(URL, "", text)]


def test_trimmed_page_parses_to_the_same_windows():
    original = keys(SPHINX_PAGE)
    used = {k for k in original if "Deprecated since" in k[3] or "Intro text" in k[3]}
    trimmed = trim_page(URL, SPHINX_PAGE, used)
    assert set(keys(trimmed)) == used
    assert "unrelated paragraph" not in trimmed and "preferred over" not in trimmed
    deprecated = next(k for k in keys(trimmed) if "Deprecated since" in k[3])
    assert deprecated[2] == "classmethod datetime.utcnow() [datetime.datetime.utcnow]"  # still under its definition


def test_unused_page_becomes_a_heading_only_placeholder():
    assert trim_page(URL, SPHINX_PAGE, set()) == PLACEHOLDER
    assert page_windows(URL, "", PLACEHOLDER) == []


def test_snippets_are_kept_only_where_they_stood_in_for_a_failed_extract():
    search = {"data": {"query": "q", "results": [
        {"url": "https://d.example/a", "title": "A", "score": 0.9, "content": "snippet a", "raw_content": None},
        {"url": "https://d.example/b", "title": "B", "score": 0.8, "content": "snippet b", "raw_content": None},
        {"url": "https://d.example/c", "title": "C", "score": 0.7, "content": "snippet c", "raw_content": None},
    ]}, "status": 200}
    extract = {"data": {"results": [{"url": "https://d.example/a", "raw_content": "# A\n\nWhole page text of A here."}],
                        "failed_results": [{"url": "https://d.example/b", "error": "timeout"}]}, "status": 200}
    out = trim_tavily({"s": search, "e": extract}, used=set(),
                      requests={"s": {"url": "https://api.tavily.com/search"}, "e": {"url": "https://api.tavily.com/extract"}})
    hits = {r["url"]: r for r in out["s"]["data"]["results"]}
    assert hits["https://d.example/a"]["content"] == ""  # extracted: the page was used, not the snippet
    assert hits["https://d.example/b"]["content"] == "snippet b"  # extract failed: the snippet was the page
    assert hits["https://d.example/c"]["content"] == ""  # never read
    assert all(h["title"] for h in hits.values())  # titles and order stay
    assert out["e"]["data"]["results"][0]["raw_content"] == PLACEHOLDER
