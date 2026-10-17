"""Licence name normalisation and comparison against registry metadata."""

from __future__ import annotations

import re
from enum import StrEnum

# Common spellings -> SPDX id. Keys are compared after lowercasing and
# collapsing punctuation to single spaces.
_ALIASES = {
    "mit": "MIT",
    "mit license": "MIT",
    "the mit license": "MIT",
    "expat": "MIT",
    "apache 2": "Apache-2.0",
    "apache 2 0": "Apache-2.0",
    "apache v2": "Apache-2.0",
    "apache license 2 0": "Apache-2.0",
    "apache license version 2 0": "Apache-2.0",
    "apache software license 2 0": "Apache-2.0",
    "asl 2 0": "Apache-2.0",
    "bsd 3 clause": "BSD-3-Clause",
    "3 clause bsd": "BSD-3-Clause",
    "new bsd": "BSD-3-Clause",
    "modified bsd": "BSD-3-Clause",
    "bsd 2 clause": "BSD-2-Clause",
    "2 clause bsd": "BSD-2-Clause",
    "simplified bsd": "BSD-2-Clause",
    "freebsd": "BSD-2-Clause",
    "0bsd": "0BSD",
    "isc": "ISC",
    "isc license": "ISC",
    "mpl 2 0": "MPL-2.0",
    "mozilla public license 2 0": "MPL-2.0",
    "gpl 2 0": "GPL-2.0",
    "gplv2": "GPL-2.0",
    "gpl v2": "GPL-2.0",
    "gpl 3 0": "GPL-3.0",
    "gplv3": "GPL-3.0",
    "gpl v3": "GPL-3.0",
    "lgpl 2 1": "LGPL-2.1",
    "lgplv2 1": "LGPL-2.1",
    "lgpl 3 0": "LGPL-3.0",
    "lgplv3": "LGPL-3.0",
    "agpl 3 0": "AGPL-3.0",
    "agplv3": "AGPL-3.0",
    "unlicense": "Unlicense",
    "the unlicense": "Unlicense",
    "cc0": "CC0-1.0",
    "cc0 1 0": "CC0-1.0",
    "psf": "PSF-2.0",
    "psf 2 0": "PSF-2.0",
    "python software foundation license": "PSF-2.0",
    "zlib": "Zlib",
    "bsl 1 0": "BSL-1.0",
    "boost software license 1 0": "BSL-1.0",
    "epl 2 0": "EPL-2.0",
    "artistic 2 0": "Artistic-2.0",
    "busl 1 1": "BUSL-1.1",
    "business source license 1 1": "BUSL-1.1",
    "elastic 2 0": "Elastic-2.0",
    "sspl 1 0": "SSPL-1.0",
}

# Names that identify a family but not one licence (no version or clause count).
_FAMILIES = {
    "apache": "Apache",
    "apache license": "Apache",
    "apache software license": "Apache",
    "bsd": "BSD",
    "bsd license": "BSD",
    "gpl": "GPL",
    "gnu general public license": "GPL",
    "gnu general public license gpl": "GPL",
    "lgpl": "LGPL",
    "gnu lesser general public license": "LGPL",
    "mpl": "MPL",
    "mozilla public license": "MPL",
}

_SUFFIX = re.compile(r"-(only|or-later)$", re.I)

KNOWN_SPDX = set(_ALIASES.values()) | {
    "AFL-3.0", "Apache-1.1", "BSD-4-Clause", "BlueOak-1.0.0", "CC-BY-4.0", "CC-BY-SA-4.0",
    "CDDL-1.0", "EPL-1.0", "EUPL-1.2", "GPL-1.0", "LGPL-2.0", "MIT-0", "MPL-1.1", "MS-PL",
    "NCSA", "OFL-1.1", "Python-2.0", "Unicode-DFS-2016", "UPL-1.0", "WTFPL",
}
_KNOWN_LOWER = {k.lower(): k for k in KNOWN_SPDX}


def _key(text: str) -> str:
    text = text.lower().replace("licence", "license")
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(licensed|osi approved|license :: osi approved)\b", " ", text)
    return " ".join(text.split())


def canonical(name: str) -> str | None:
    """SPDX id for a licence name, or None if unknown. GPL-3.0-only -> GPL-3.0."""
    stripped = name.strip()
    if not stripped:
        return None
    if stripped.lower().startswith("license :: "):
        stripped = stripped.split("::")[-1]
    k = _key(stripped)
    if k in _ALIASES:
        return _ALIASES[k]
    if k.endswith(" license") and k[: -len(" license")] in _ALIASES:
        return _ALIASES[k[: -len(" license")]]
    # Already an SPDX id? (GPL-3.0-only, GPL-3.0-or-later and GPL-3.0+ map to GPL-3.0)
    if re.fullmatch(r"[A-Za-z0-9.+-]+", stripped):
        base = _SUFFIX.sub("", stripped.rstrip("+"))
        return _KNOWN_LOWER.get(base.lower())
    return None


def family(name: str) -> str | None:
    k = _key(name.split("::")[-1]) if "::" in name else _key(name)
    if k.endswith(" license") and k not in _FAMILIES:
        k2 = k[: -len(" license")]
        if k2 in _FAMILIES:
            return _FAMILIES[k2]
    if k in _FAMILIES:
        return _FAMILIES[k]
    c = canonical(name)
    if c:
        return re.split(r"[-]", c)[0]
    return None


def detect_license_text(text: str) -> str | None:
    """Recognise a pasted licence body (PyPI's `license` field sometimes holds one)."""
    t = " ".join(text.split()).lower()
    if "permission is hereby granted, free of charge" in t:
        return "MIT"
    if "apache license" in t and "version 2.0" in t:
        return "Apache-2.0"
    if "redistribution and use in source and binary forms" in t:
        if "neither the name" in t or "names of its contributors" in t:
            return "BSD-3-Clause"
        return "BSD-2-Clause"
    if "permission to use, copy, modify, and/or distribute this software" in t:
        return "ISC"
    return None


class Match(StrEnum):
    MATCH = "match"
    MISMATCH = "mismatch"
    PARTIAL = "partial"  # claimed licence is one part of an AND expression
    UNKNOWN = "unknown"


def split_expression(expr: str) -> tuple[list[str], set[str]]:
    """Licence ids and the operators of an SPDX expression."""
    tokens = re.split(r"\s+(AND|OR|WITH)\s+|[()]", expr, flags=re.I)
    ids, ops = [], set()
    for tok in tokens:
        if not tok or not tok.strip():
            continue
        if tok.upper() in ("AND", "OR", "WITH"):
            ops.add(tok.upper())
        else:
            ids.append(tok.strip())
    return ids, ops


def compare_license(claimed: str, actual: str) -> Match:
    """Compare a claimed licence with one metadata value."""
    if claimed.strip().lower() == actual.strip().lower():
        return Match.MATCH
    claimed_id = canonical(claimed)
    claimed_family = family(claimed)
    claimed_is_family_only = claimed_id is None or _key(claimed) in _FAMILIES

    if len(actual) > 200:  # a pasted licence body
        detected = detect_license_text(actual)
        if not detected:
            return Match.UNKNOWN
        actual = detected

    ids, ops = split_expression(actual)
    if len(ids) > 1 and ops:
        hits = [i for i in ids if _same(claimed_id, claimed_family, claimed_is_family_only, i) == Match.MATCH]
        if not hits:
            if all(canonical(i) for i in ids):
                return Match.MISMATCH
            return Match.UNKNOWN
        if ops == {"OR"}:
            return Match.MATCH
        return Match.PARTIAL
    return _same(claimed_id, claimed_family, claimed_is_family_only, actual)


def _same(claimed_id: str | None, claimed_family: str | None, family_only: bool, actual: str) -> Match:
    actual_family_name = _key(actual.split("::")[-1]) if "::" in actual else _key(actual)
    actual_is_family_only = actual_family_name in _FAMILIES or (
        actual_family_name.endswith(" license") and actual_family_name[: -len(" license")] in _FAMILIES
    )
    actual_id = None if actual_is_family_only else canonical(actual)
    actual_family = family(actual)

    if actual_id is None and actual_family is None:
        return Match.UNKNOWN
    if not family_only and actual_id:
        if claimed_id and claimed_id.lower() == actual_id.lower():
            return Match.MATCH
        return Match.MISMATCH
    # One side names only a family ("BSD", "Apache Software License").
    if claimed_family and actual_family:
        if claimed_family.lower() != actual_family.lower():
            return Match.MISMATCH
        if family_only:
            return Match.MATCH  # "BSD" vs "BSD-3-Clause": the claim is less specific, still true
        return Match.UNKNOWN  # "BSD-3-Clause" vs "BSD License": metadata is too vague
    return Match.UNKNOWN
