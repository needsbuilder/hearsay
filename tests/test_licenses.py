import pytest

from hearsay.licenses import Match, canonical, compare_license


@pytest.mark.parametrize(
    "name,spdx",
    [
        ("MIT", "MIT"),
        ("MIT License", "MIT"),
        ("Apache 2.0", "Apache-2.0"),
        ("Apache License, Version 2.0", "Apache-2.0"),
        ("BSD 3-Clause", "BSD-3-Clause"),
        ("GPL-3.0-or-later", "GPL-3.0"),
        ("GPLv3", "GPL-3.0"),
        ("License :: OSI Approved :: MIT License", "MIT"),
        ("UNKNOWN", None),
        ("Dual License", None),
    ],
)
def test_canonical(name, spdx):
    assert canonical(name) == spdx


@pytest.mark.parametrize(
    "claimed,actual,expected",
    [
        ("MIT", "MIT", Match.MATCH),
        ("MIT", "Apache-2.0", Match.MISMATCH),
        ("Apache 2.0", "Apache-2.0", Match.MATCH),
        # family-only metadata cannot confirm a specific licence
        ("Apache 2.0", "License :: OSI Approved :: Apache Software License", Match.UNKNOWN),
        ("BSD-3-Clause", "License :: OSI Approved :: BSD License", Match.UNKNOWN),
        # a family-only claim is true of a specific member of the family
        ("BSD", "BSD-3-Clause", Match.MATCH),
        ("BSD", "MIT", Match.MISMATCH),
        ("MIT", "MIT OR Apache-2.0", Match.MATCH),
        ("MIT", "(MIT AND Zlib)", Match.PARTIAL),
        ("ISC", "MIT OR Apache-2.0", Match.MISMATCH),
        ("MIT", "UNKNOWN", Match.UNKNOWN),
        ("MIT", "Dual License", Match.UNKNOWN),
    ],
)
def test_compare(claimed, actual, expected):
    assert compare_license(claimed, actual) == expected


def test_pasted_licence_body_is_recognised():
    body = (
        "Permission is hereby granted, free of charge, to any person obtaining a copy of this software "
        "and associated documentation files (the \"Software\"), to deal in the Software without restriction, "
        "including without limitation the rights to use, copy, modify, merge, publish, distribute."
    )
    assert compare_license("MIT", body) == Match.MATCH
    assert compare_license("Apache-2.0", body) == Match.MISMATCH
