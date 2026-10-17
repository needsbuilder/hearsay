from hearsay.models import Passage
from hearsay.quotes import display_quote, find_quote, normalize, quote_problem

EVIDENCE = (
    "## Timeouts\u00b6\n\nYou can tell Requests to stop waiting for a response after a given number of\n"
    "seconds with the `timeout` parameter. It\u2019s a \u201cconnect\u201d timeout, see [the docs](https://example.org/x)."
)


def test_exact_quote():
    assert quote_problem("stop waiting for a response after a given number of", EVIDENCE) is None


def test_whitespace_and_line_breaks_are_normalised():
    assert quote_problem("after a given   number of seconds with the", EVIDENCE) is None


def test_markdown_code_marks_are_ignored():
    assert quote_problem("seconds with the timeout parameter", EVIDENCE) is None
    assert quote_problem("seconds with the `timeout` parameter.", EVIDENCE) is None


def test_curly_and_straight_quotes_are_equivalent():
    assert quote_problem('It\'s a "connect" timeout', EVIDENCE) is None


def test_link_text_matches_without_target():
    assert quote_problem('"connect" timeout, see the docs', EVIDENCE) is None


def test_paraphrase_is_rejected():
    assert quote_problem("You can make Requests stop waiting for a response", EVIDENCE) == "quote does not appear in the evidence"


def test_ellipsis_spanning_text_is_rejected():
    problem = quote_problem("You can tell Requests ... the timeout parameter", EVIDENCE)
    assert "ellipsis" in problem


def test_too_short_or_missing():
    assert quote_problem("timeout", EVIDENCE).startswith("quote is shorter")
    assert quote_problem("", EVIDENCE) == "no quote given"
    assert quote_problem(None, EVIDENCE) == "no quote given"


def test_find_quote_prefers_named_passage_and_reports_real_location():
    passages = [
        Passage(id=1, url="https://a.example/1", text="nothing relevant here at all"),
        Passage(id=2, url="https://a.example/2", text=EVIDENCE),
    ]
    found, problem = find_quote("stop waiting for a response after", passages, preferred=1)
    assert problem is None and found.url == "https://a.example/2"


def test_normalize_and_display():
    assert normalize("a\u00a0b\u2014c") == "a b-c"
    assert display_quote("It was [removed in 3.12](../x.html) after") == "It was removed in 3.12 after"


def test_single_and_double_quote_marks_are_the_same_character():
    evidence = 'Call it with timeout=None to wait forever, or use the value "connect" for the first phase.'
    assert quote_problem("or use the value 'connect' for the first phase", evidence) is None
    assert quote_problem("or use the value \u2018connect\u2019 for the first phase", evidence) is None
    assert quote_problem("or use the value \u201cconnect\u201d for the first phase", evidence) is None
    # nothing fuzzier: other characters still have to match
    assert quote_problem("or use the value `connect` for the first phases", evidence) is not None
    assert quote_problem("or use the value (connect) for the first phase", evidence) is not None
