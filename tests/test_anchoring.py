"""The anchoring rule: written forms, the API-heading rule, and page sections."""

import pytest

from hearsay.anchoring import Anchor, is_api_heading
from hearsay.models import Passage
from hearsay.passages import page_sections, page_windows


def named(symbol: str, text: str) -> bool:
    return Anchor.parse(symbol).named_in(text)


@pytest.mark.parametrize(
    "text",
    [
        "Use `fs.rm(path, { recursive: true })`.",
        "fs.rm removes files and directories.",
        "#### `fsPromises.rm(path[, options])`",
        "await fs.promises.rm(dir)",
    ],
)
def test_fs_rm_written_forms(text):
    assert named("fs.rm", text)


@pytest.mark.parametrize(
    "text",
    [
        "#### `fs.rmdir(path[, options], callback)`",
        "fs.rmSync(path)",
        "rm(path[, options])",  # a bare name needs a heading that names fs.rm
        "the rm utility",
        "xfs.rm(path)",
    ],
)
def test_fs_rm_other_names(text):
    assert not named("fs.rm", text)


def test_python_forms():
    assert named("datetime.utcnow()", "classmethod datetime.utcnow()")
    assert named("datetime.utcnow", "datetime.datetime.utcnow() is deprecated")
    assert named("datetime.utcnow", "`datetime.datetime`\u2019s `utcnow()` and `utcfromtimestamp()` are deprecated")
    assert named("datetime.utcnow", 'see [`utcnow()`](../library/datetime.html#datetime.datetime.utcnow "datetime.datetime.utcnow")')
    assert not named("datetime.utcnow", "datetime.utcfromtimestamp(ts)")
    assert not named("datetime.utcnow", "utcnow() returns a naive datetime")
    # Tavily's Markdown puts a space after the dot in code samples
    assert named("requests.get", ">>> requests. get('https://github.com', timeout=0.001)")
    assert not named("requests.get", "requests. Get the session first.")
    assert not named("requests.get", "requests.getaddrinfo")
    # a module is named by its bare name
    assert named("distutils", "Remove the `distutils` package.")
    assert not named("distutils", "the distutils2 project")


def test_symbol_parsing():
    assert Anchor.parse("`fs.rm(path[, options])`").parts == ("fs", "rm")
    assert Anchor.parse("Array.prototype.at()").written_forms() == ["Array.prototype.at", "prototype.at"]
    assert Anchor.parse("Stripe refunds") is None  # not an identifier: no anchoring


def test_api_headings():
    assert is_api_heading("`fs.rm(path[, options], callback)`")
    assert is_api_heading("Array.prototype.at()")
    assert not is_api_heading("Timeouts")
    assert not is_api_heading("Python (programming language)")


def test_api_heading_decides_alone():
    rm = Anchor.parse("fs.rm")
    rmdir_section = Passage(
        id=1,
        url="https://nodejs.org/api/fs.html",
        section=["File system", "fs.rmdir(path[, options], callback)"],
        api_heading="fs.rmdir(path[, options], callback)",
        text="| v14.14.0 | The `recursive` option is deprecated, use `fs.rm` instead. |",
    )
    assert "section for 'fs.rmdir(path[, options], callback)'" in rm.problem(rmdir_section)
    rm_section = rmdir_section.model_copy(update={"api_heading": "fs.rm(path[, options], callback)", "text": "`recursive` If true..."})
    assert rm.problem(rm_section) is None


def test_prose_sections_need_the_name_in_heading_or_text():
    rm = Anchor.parse("fs.rm")
    prose = Passage(id=1, url="u", section=["Deprecations", "DEP0147"], text="Use fs.rm(path, { recursive: true }) instead.")
    assert rm.problem(prose) is None
    unrelated = prose.model_copy(update={"text": "Recursive removal is retried on failure."})
    assert rm.problem(unrelated) == "the quoted passage does not name fs.rm"


SPHINX = """# `datetime` Objects[\u00b6](#datetime-objects "Link to this heading")

Intro text about datetime objects.

*classmethod* datetime.now(*tz=None*)[\u00b6](#datetime.datetime.now "Link to this definition")
:   Return the current local date and time.

    This function is preferred over [`utcnow()`](#datetime.datetime.utcnow "datetime.datetime.utcnow").

*classmethod* datetime.utcnow()[\u00b6](#datetime.datetime.utcnow "Link to this definition")
:   Return the current UTC date and time.

    Deprecated since version 3.12: Use `datetime.now()` with `UTC` instead.

Text after the definitions belongs to the section again.
"""


def test_sphinx_definitions_become_headings():
    sections = page_sections(SPHINX)
    paths = [[h.text for h in hs] for hs, _ in sections]
    assert paths == [
        ["datetime Objects"],
        ["datetime Objects", "classmethod datetime.now(tz=None) [datetime.datetime.now]"],
        ["datetime Objects", "classmethod datetime.utcnow() [datetime.datetime.utcnow]"],
        ["datetime Objects"],
    ]
    windows = page_windows("u", "", SPHINX)
    assert windows[-1].api_heading is None
    deprecated = next(w for w in windows if "Deprecated since" in w.text)
    assert deprecated.api_heading == "classmethod datetime.utcnow() [datetime.datetime.utcnow]"


def test_markdown_headings_nest_and_drop_permalinks():
    md = (
        "# Page\n\n## `fs.rm(path)`[#](#fsrm)\n\nBody one, long enough to keep.\n\n### Example\n\n"
        "Body two, long enough to keep.\n\n## Other\n\nBody three, long enough to keep."
    )
    paths = [[h.text for h in hs] for hs, _ in page_sections(md)]
    assert paths == [["Page", "fs.rm(path)"], ["Page", "fs.rm(path)", "Example"], ["Page", "Other"]]
    example = page_windows("u", "", md)[1]
    assert example.api_heading == "fs.rm(path)"  # the nearest API heading, not the nearest heading
