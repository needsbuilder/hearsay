"""Data models shared by every stage: claims, verdicts, results and the report."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ClaimType(StrEnum):
    PACKAGE_EXISTS = "package_exists"
    VERSION_EXISTS = "version_exists"
    FIXES_VULNERABILITY = "fixes_vulnerability"
    AFFECTED_BY_VULNERABILITY = "affected_by_vulnerability"
    LICENSE_IS = "license_is"
    DEPRECATED = "deprecated"
    PARAMETER_EXISTS = "parameter_exists"
    API_BEHAVIOR = "api_behavior"
    OTHER_EXTERNAL = "other_external"


class Verdict(StrEnum):
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"


class DecisionPath(StrEnum):
    """Which part of Hearsay decided a claim."""

    REGISTRY = "registry"  # PyPI, npm or deps.dev metadata, no model
    ADVISORY = "advisory"  # OSV advisory data, no model
    JURY = "jury"  # docs evidence, judges agreed
    ADJUDICATOR = "adjudicator"  # docs evidence, judges disagreed
    NONE = "none"  # nothing decided it (no source, skipped, error)


# Fields every claim may carry. Which ones are required depends on the type
# (see REQUIRED_FIELDS). Values are copied from the input, never guessed.
CLAIM_FIELDS = (
    "ecosystem",
    "package",
    "version",
    "vulnerability_id",
    "license",
    "symbol",
    "parameter",
    "since_version",
    "subject",
)

REQUIRED_FIELDS: dict[ClaimType, tuple[tuple[str, ...], ...]] = {
    # each inner tuple is "at least one of"
    ClaimType.PACKAGE_EXISTS: (("package",),),
    ClaimType.VERSION_EXISTS: (("package",), ("version",)),
    ClaimType.FIXES_VULNERABILITY: (("package",), ("version",), ("vulnerability_id",)),
    ClaimType.AFFECTED_BY_VULNERABILITY: (("package",), ("version",)),
    ClaimType.LICENSE_IS: (("package",), ("license",)),
    ClaimType.DEPRECATED: (("symbol", "package"),),
    ClaimType.PARAMETER_EXISTS: (("symbol",), ("parameter",)),
    ClaimType.API_BEHAVIOR: (("subject", "package", "symbol"),),
    ClaimType.OTHER_EXTERNAL: (),
}


class Claim(BaseModel):
    """One atomic, checkable statement about a third-party fact."""

    model_config = ConfigDict(extra="forbid")

    id: str = ""
    type: ClaimType
    statement: str = Field(min_length=3)
    source_sentence: str = Field(min_length=1)
    ecosystem: str | None = None
    package: str | None = None
    version: str | None = None
    vulnerability_id: str | None = None
    license: str | None = None
    symbol: str | None = None
    parameter: str | None = None
    since_version: str | None = None
    subject: str | None = None
    negated: bool = False
    origin: str = "llm"  # "llm" or "pattern" (install commands and pins found without a model)

    def missing_fields(self) -> list[str]:
        missing = []
        for group in REQUIRED_FIELDS[self.type]:
            if not any(getattr(self, name) for name in group):
                missing.append(" or ".join(group))
        return missing


class Passage(BaseModel):
    """A piece of documentation text shown to the jury."""

    id: int
    url: str
    title: str = ""
    text: str


class JudgeVote(BaseModel):
    model: str
    role: str  # "judge" or "adjudicator"
    verdict: Verdict  # effective verdict, after the quote rule
    stated_verdict: Verdict | None = None  # what the model said; None if its output was invalid
    quote: str | None = None
    quote_found: bool = False
    url: str | None = None
    reasoning: str = ""
    error: str | None = None


class ClaimResult(BaseModel):
    claim: Claim
    verdict: Verdict
    path: DecisionPath
    source_url: str | None = None
    quote: str | None = None
    reason: str = ""
    judges: list[JudgeVote] = Field(default_factory=list)
    adjudicator: JudgeVote | None = None
    docs_domains: list[str] = Field(default_factory=list)
    evidence: list[Passage] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class RejectedClaim(BaseModel):
    """Model output that failed validation and was dropped."""

    raw: dict | str
    errors: list[str]


class ExtractionInfo(BaseModel):
    method: str  # "llm" or "patterns"
    model: str | None = None
    sentences: int = 0
    rejected: list[RejectedClaim] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class Totals(BaseModel):
    claims: int = 0
    supported: int = 0
    contradicted: int = 0
    unverifiable: int = 0


class Usage(BaseModel):
    http_requests: int = 0
    http_cache_hits: int = 0
    tavily_calls: int = 0
    tavily_cache_hits: int = 0
    llm_calls: int = 0
    llm_cache_hits: int = 0


class ModelConfig(BaseModel):
    llm_base_url: str | None = None
    extract_model: str | None = None
    judge_models: list[str] = Field(default_factory=list)
    adjudicator_model: str | None = None


class Report(BaseModel):
    hearsay_version: str
    totals: Totals
    results: list[ClaimResult]
    extraction: ExtractionInfo
    models: ModelConfig
    usage: Usage
    input_title: str | None = None
    input_url: str | None = None

    @staticmethod
    def count(results: list[ClaimResult]) -> Totals:
        t = Totals(claims=len(results))
        for r in results:
            setattr(t, r.verdict.value, getattr(t, r.verdict.value) + 1)
        return t
