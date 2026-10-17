from hearsay.models import ClaimType
from hearsay.patterns import extract_with_patterns, pinned_claims
from hearsay.pipeline import add_missed_pins

from support import claim


def kinds(text):
    claims, _ = extract_with_patterns(text)
    return [(c.type, c.package, c.version, c.vulnerability_id or c.license, c.ecosystem) for c in claims]


def test_fix_claim_with_to_phrase():
    assert kinds("Bumped requests to 2.31.0, which fixes CVE-2023-32681.") == [
        (ClaimType.FIXES_VULNERABILITY, "requests", "2.31.0", "CVE-2023-32681", None)
    ]


def test_install_commands():
    out = kinds("Run `npm install express@4.21.2 left-pad` first.")
    assert (ClaimType.VERSION_EXISTS, "express", "4.21.2", None, "npm") in out
    assert (ClaimType.PACKAGE_EXISTS, "left-pad", None, None, "npm") in out
    assert kinds("pip install fastapi==0.200.0")[0][:3] == (ClaimType.VERSION_EXISTS, "fastapi", "0.200.0")


def test_install_command_in_prose_stops_at_the_clause():
    out = kinds("Run pip install requests==2.31.0, which fixes CVE-2023-32681.")
    assert (ClaimType.VERSION_EXISTS, "requests", "2.31.0", None, "pypi") in out
    assert (ClaimType.FIXES_VULNERABILITY, "requests", "2.31.0", "CVE-2023-32681", "pypi") in out
    assert {p for _, p, _, _, _ in out} == {"requests"}
    assert [p for _, p, _, _, _ in kinds("pip install fastapi and uvicorn, then restart the server.")] == ["fastapi", "uvicorn"]


def test_install_command_stops_where_the_prose_starts():
    # Without punctuation: "to" starts the prose, so "get", "new" and "router" are not packages.
    assert [p for _, p, _, _, _ in kinds("Run pip install fastapi==0.200.0 to get the new router.")] == ["fastapi"]
    assert [p for _, p, _, _, _ in kinds("npm install left-pad for the string helper")] == ["left-pad"]


def test_licence_phrase_needs_one_package():
    assert kinds("The `httpx` package is BSD-3-Clause licensed.") == [
        (ClaimType.LICENSE_IS, "httpx", None, "BSD-3-Clause", None)
    ]
    assert kinds("This library is MIT licensed.") == []


def test_dependabot_bump():
    out = kinds("Bumps [urllib3](https://github.com/urllib3/urllib3) from 2.1.0 to 2.8.0.")
    assert [(k, p, v) for k, p, v, _, _ in out] == [
        (ClaimType.VERSION_EXISTS, "urllib3", "2.1.0"),
        (ClaimType.VERSION_EXISTS, "urllib3", "2.8.0"),
    ]


def test_python_version_is_not_a_package():
    assert kinds("This works on Python 3.12 and later.") == []


def test_pins_only_ignores_prose_versions():
    assert pinned_claims("Bumped requests to 2.31.0.") == []
    assert [c.package for c in pinned_claims("Added `fastapi==0.200.0`.")] == ["fastapi"]


def test_missed_pins_are_added_once():
    text = "Added `fastapi==0.200.0` and `requests==2.31.0`."
    existing = [claim("version_exists", "requests 2.31.0 exists", package="requests", version="2.31.0",
                      source_sentence=text)]
    out = add_missed_pins(existing, text)
    assert [(c.package, c.origin) for c in out] == [("requests", "llm"), ("fastapi", "pattern")]
