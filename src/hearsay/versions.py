"""Version parsing and comparison, and OSV range evaluation.

PyPI versions follow PEP 440 (packaging.version). npm versions follow
Semantic Versioning 2.0.0, implemented here so pre-release ordering is exact.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from typing import Any

from packaging.version import InvalidVersion, Version


class VersionError(ValueError):
    pass


_SEMVER_RE = re.compile(
    r"^[v=]*\s*(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


@functools.total_ordering
@dataclass(frozen=True)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[int | str, ...] = ()

    @classmethod
    def parse(cls, text: str) -> "SemVer":
        m = _SEMVER_RE.match(text.strip())
        if not m:
            raise VersionError(f"not a semantic version: {text!r}")
        pre: tuple[int | str, ...] = ()
        if m.group(4):
            pre = tuple(int(p) if p.isdigit() else p for p in m.group(4).split("."))
        return cls(int(m.group(1)), int(m.group(2)), int(m.group(3)), pre)

    def _key(self) -> tuple:
        # A release sorts after all of its pre-releases. Within a pre-release,
        # numeric identifiers sort before alphanumeric ones, numbers compare
        # numerically, strings in ASCII order, and a shorter list of equal
        # identifiers sorts first (SemVer 2.0.0, section 11).
        if not self.prerelease:
            pre_key: tuple = (1,)
        else:
            pre_key = (0, tuple((0, p, "") if isinstance(p, int) else (1, 0, p) for p in self.prerelease))
        return (self.major, self.minor, self.patch, pre_key)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._key() < other._key()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._key() == other._key()

    def __hash__(self) -> int:
        return hash(self._key())


def normalize_ecosystem(value: str | None) -> str | None:
    """Map free-form ecosystem names to 'pypi' or 'npm'; other names pass through lowercased."""
    if not value:
        return None
    v = value.strip().lower()
    if v in {"pypi", "pip", "python", "py"}:
        return "pypi"
    if v in {"npm", "node", "nodejs", "node.js", "javascript", "js", "typescript", "ts", "yarn", "pnpm"}:
        return "npm"
    return v


def parse_version(ecosystem: str, text: str) -> Version | SemVer:
    if ecosystem == "pypi":
        try:
            return Version(text)
        except InvalidVersion:
            raise VersionError(f"not a PEP 440 version: {text!r}") from None
    if ecosystem == "npm":
        return SemVer.parse(text)
    raise VersionError(f"unsupported ecosystem: {ecosystem}")


def compare(ecosystem: str, a: str, b: str) -> int:
    va, vb = parse_version(ecosystem, a), parse_version(ecosystem, b)
    return (va > vb) - (va < vb)


def versions_equal(ecosystem: str, a: str, b: str) -> bool:
    try:
        return compare(ecosystem, a, b) == 0
    except VersionError:
        return a.strip() == b.strip()


# ---------------------------------------------------------------- OSV ranges


class _Min:
    """Sorts before every version: OSV's `introduced: "0"`."""

    def __lt__(self, other: object) -> bool:
        return not isinstance(other, _Min)

    def __gt__(self, other: object) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _Min)

    def __hash__(self) -> int:
        return 0


_MIN = _Min()
_EVENT_KINDS = ("introduced", "fixed", "last_affected", "limit")


def _event_version(ecosystem: str, value: str) -> Any:
    return _MIN if value == "0" else parse_version(ecosystem, value)


def range_affects(ecosystem: str, version: str, events: list[dict[str, str]]) -> bool:
    """Is `version` inside an OSV range given by its events?

    Follows the evaluation in the OSV schema: sort the events by version
    (`introduced: "0"` first) and walk them; the last event at or below the
    version decides. `last_affected` is inclusive, `fixed` and `limit` are
    exclusive upper bounds.
    """
    v = parse_version(ecosystem, version)
    flat: list[tuple[Any, int, str]] = []
    for idx, event in enumerate(events):
        for kind in _EVENT_KINDS:
            if kind in event:
                flat.append((_event_version(ecosystem, event[kind]), idx, kind))
    flat.sort(key=functools.cmp_to_key(_cmp_events))

    affected = False
    for ev_version, _, kind in flat:
        if kind == "introduced":
            if ev_version is _MIN or v >= ev_version:
                affected = True
        elif kind in ("fixed", "limit"):
            if v >= ev_version:
                affected = False
        elif kind == "last_affected":
            if v > ev_version:
                affected = False
    return affected


def _cmp_events(a: tuple, b: tuple) -> int:
    va, vb = a[0], b[0]
    if va < vb:
        return -1
    if vb < va:
        return 1
    return (a[1] > b[1]) - (a[1] < b[1])


# OSV range types whose events are package versions for each ecosystem.
_RANGE_TYPES = {"pypi": {"ECOSYSTEM"}, "npm": {"SEMVER", "ECOSYSTEM"}}


@dataclass
class AffectedCheck:
    affected: bool
    used: list[dict]  # the ranges (or explicit version list) that decided it


def affected_entry_covers(ecosystem: str, version: str, entry: dict) -> AffectedCheck | None:
    """Evaluate one OSV `affected[]` entry. None if it has nothing usable."""
    usable = [r for r in entry.get("ranges", []) if r.get("type") in _RANGE_TYPES.get(ecosystem, set())]
    explicit = entry.get("versions") or []
    if not usable and not explicit:
        return None
    for rng in usable:
        if range_affects(ecosystem, version, rng.get("events", [])):
            return AffectedCheck(True, [rng])
    for listed in explicit:
        if versions_equal(ecosystem, listed, version):
            return AffectedCheck(True, [{"versions": [listed]}])
    return AffectedCheck(False, usable or [{"versions": explicit[:20]}])


def range_bounds(ecosystem: str, rng: dict) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {k: [] for k in _EVENT_KINDS}
    for event in rng.get("events", []):
        for kind in _EVENT_KINDS:
            if kind in event:
                out[kind].append(event[kind])
    return out
