import pytest

from hearsay.versions import (
    SemVer,
    VersionError,
    affected_entry_covers,
    compare,
    normalize_ecosystem,
    range_affects,
)


# ---------------------------------------------------------------- PEP 440


@pytest.mark.parametrize(
    "a,b",
    [
        ("2.31.0rc1", "2.31.0"),
        ("2.31.0a1", "2.31.0b1"),
        ("2.31.0b2", "2.31.0rc1"),
        ("2.31.0.dev1", "2.31.0a1"),
        ("2.31.0", "2.31.0.post1"),
        ("1.9", "1.10"),
        ("1!0.1", "1!0.2"),
        ("2.0", "1!0.1"),
    ],
)
def test_pypi_ordering(a, b):
    assert compare("pypi", a, b) == -1
    assert compare("pypi", b, a) == 1


def test_pypi_equal_with_trailing_zeros():
    assert compare("pypi", "2.31", "2.31.0") == 0


def test_pypi_invalid():
    with pytest.raises(VersionError):
        compare("pypi", "not-a-version", "1.0")


# ---------------------------------------------------------------- SemVer


def test_semver_precedence_chain_from_spec():
    # SemVer 2.0.0, section 11
    chain = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
    ]
    parsed = [SemVer.parse(v) for v in chain]
    assert parsed == sorted(parsed)
    for lower, higher in zip(chain, chain[1:]):
        assert compare("npm", lower, higher) == -1


def test_semver_build_metadata_ignored_and_prefix_accepted():
    assert compare("npm", "1.2.3+build.5", "1.2.3") == 0
    assert compare("npm", "v1.2.3", "1.2.3") == 0


def test_semver_numeric_not_lexical():
    assert compare("npm", "4.17.9", "4.17.21") == -1


def test_semver_invalid():
    with pytest.raises(VersionError):
        SemVer.parse("4.17")


def test_normalize_ecosystem():
    assert normalize_ecosystem("PyPI") == "pypi"
    assert normalize_ecosystem("Node.js") == "npm"
    assert normalize_ecosystem("crates.io") == "crates.io"
    assert normalize_ecosystem(None) is None


# ---------------------------------------------------------------- OSV ranges


def test_simple_range():
    events = [{"introduced": "2.3.0"}, {"fixed": "2.31.0"}]
    assert range_affects("pypi", "2.30.0", events)
    assert range_affects("pypi", "2.3.0", events)  # introduced is inclusive
    assert not range_affects("pypi", "2.31.0", events)  # fixed is exclusive
    assert not range_affects("pypi", "2.2.9", events)


def test_introduced_zero():
    assert range_affects("pypi", "0.0.1", [{"introduced": "0"}, {"fixed": "1.0"}])
    assert range_affects("npm", "0.0.0-alpha", [{"introduced": "0"}, {"fixed": "1.0.0"}])


def test_pre_release_of_fixed_version_is_affected():
    events = [{"introduced": "0"}, {"fixed": "2.31.0"}]
    assert range_affects("pypi", "2.31.0rc1", events)
    assert range_affects("npm", "2.31.0-rc.1", [{"introduced": "0"}, {"fixed": "2.31.0"}])


def test_multiple_events_reintroduced():
    events = [{"introduced": "0"}, {"fixed": "1.2.0"}, {"introduced": "1.5.0"}, {"fixed": "1.7.0"}]
    assert range_affects("npm", "1.1.9", events)
    assert not range_affects("npm", "1.2.0", events)
    assert not range_affects("npm", "1.4.99", events)
    assert range_affects("npm", "1.5.0", events)
    assert range_affects("npm", "1.6.3", events)
    assert not range_affects("npm", "1.7.0", events)


def test_unsorted_events_are_sorted_first():
    events = [{"fixed": "1.7.0"}, {"introduced": "1.5.0"}, {"fixed": "1.2.0"}, {"introduced": "0"}]
    assert range_affects("pypi", "1.6", events)
    assert not range_affects("pypi", "1.3", events)


def test_last_affected_is_inclusive():
    events = [{"introduced": "0"}, {"last_affected": "4.5.0"}]
    assert range_affects("npm", "4.5.0", events)
    assert not range_affects("npm", "4.5.1", events)
    assert not range_affects("npm", "4.6.0-rc.0", events)


def test_limit_is_an_upper_bound():
    events = [{"introduced": "1.0"}, {"limit": "2.0"}]
    assert range_affects("pypi", "1.5", events)
    assert not range_affects("pypi", "2.0", events)


def test_affected_entry_uses_matching_range_types_only():
    entry = {
        "ranges": [
            {"type": "GIT", "events": [{"introduced": "0"}, {"fixed": "abc123"}]},
            {"type": "ECOSYSTEM", "events": [{"introduced": "2.3.0"}, {"fixed": "2.31.0"}]},
        ]
    }
    assert affected_entry_covers("pypi", "2.30.0", entry).affected
    assert not affected_entry_covers("pypi", "2.31.0", entry).affected


def test_affected_entry_explicit_versions_only():
    entry = {"versions": ["1.0.0", "1.0.1"]}
    assert affected_entry_covers("npm", "1.0.1", entry).affected
    assert not affected_entry_covers("npm", "1.0.2", entry).affected
    assert affected_entry_covers("npm", "1.0.0", {"ranges": [{"type": "GIT", "events": []}]}) is None
