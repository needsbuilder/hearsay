"""Hearsay: check what coding agents claim about the outside world against primary sources.

    import hearsay
    report = hearsay.check("requests 2.31.0 fixes CVE-2023-32681.")
    print(hearsay.to_markdown(report))
"""

from ._version import __version__
from .config import Settings, load_env_file
from .models import Claim, ClaimResult, ClaimType, DecisionPath, Report, Verdict
from .pipeline import ConfigError, Context, check, check_claim, check_claims
from .report import to_json, to_markdown

__all__ = [
    "__version__",
    "Claim",
    "ClaimResult",
    "ClaimType",
    "ConfigError",
    "Context",
    "DecisionPath",
    "Report",
    "Settings",
    "Verdict",
    "check",
    "check_claim",
    "check_claims",
    "load_env_file",
    "to_json",
    "to_markdown",
]
