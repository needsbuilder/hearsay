"""MCP server: a coding agent checks a statement before making it.

    hearsay mcp                     # stdio transport

Tools:
- hearsay_check(text): every claim about third-party facts in a text (a draft
  pull request description, an answer about to be sent).
- hearsay_claim(sentence): one statement, for example
  "requests 2.31.0 fixes CVE-2023-32681".

Both return structured results (verdict, decision path, source URL, quote,
reason per claim) and a short text summary. Settings come from environment
variables (the MCP client's `env` block) or `hearsay mcp --env-file PATH`;
without model settings the tools fall back to the pattern extractor and
check registry and advisory claims only.
"""

from __future__ import annotations

from typing import Annotated, Callable, Literal

from mcp.server import MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BaseModel, Field

from ._version import __version__
from .config import Settings
from .models import Report
from .pipeline import ConfigError, Context, check

INSTRUCTIONS = """Hearsay checks statements about the outside world against primary sources:
package and version existence (PyPI, npm), which version fixes a CVE (OSV), licences (deps.dev,
registries), npm deprecations, and documented parameters, deprecations and API behaviour (the
official documentation, judged by a jury of models with a verbatim-quote rule).

Call hearsay_claim before you state such a fact, and hearsay_check on a pull request description
or answer before you send it. "contradicted" means a primary source says otherwise: do not make
the statement, use the source instead. "unverifiable" means no primary source confirmed it: say
so, or leave it out. Claims about your own work (tests pass, refactors) are not checked."""

MAX_SUMMARY_QUOTE = 240


class ClaimCheck(BaseModel):
    id: str
    statement: str = Field(description="The claim as Hearsay understood it.")
    type: str = Field(description="Claim type, for example fixes_vulnerability or parameter_exists.")
    verdict: Literal["supported", "contradicted", "unverifiable"]
    path: Literal["registry", "advisory", "jury", "adjudicator", "none"] = Field(
        description="What decided it: registry or advisory data (no model), the jury, the adjudicator, or nothing."
    )
    source_url: str | None = Field(description="The primary source the verdict rests on.")
    quote: str | None = Field(description="Verbatim text (or field and value) from the source.")
    reason: str
    source_sentence: str = Field(description="The sentence of the input the claim came from.")


class Totals(BaseModel):
    claims: int
    supported: int
    contradicted: int
    unverifiable: int


class CheckOutput(BaseModel):
    totals: Totals
    claims: list[ClaimCheck]
    models_used: bool = Field(description="False when model settings are missing and only patterns were used.")
    notes: list[str] = Field(default_factory=list)


ContextFactory = Callable[[], tuple[Context, list[str]]]


def default_context() -> tuple[Context, list[str]]:
    """A context from the environment; without model settings, a no-model context and a note."""
    settings = Settings.from_env()
    problems = settings.llm_problems()
    if not problems:
        return Context.create(settings, use_llm=True), []
    note = (
        "Model settings are missing (" + "; ".join(problems) + "), so claims were found by patterns only "
        "(install commands, version pins, 'fixes CVE-...' sentences, licence phrases, npm deprecations) and "
        "documentation claims were not checked."
    )
    return Context.create(settings, use_llm=False), [note]


def to_output(report: Report, models_used: bool, notes: list[str]) -> CheckOutput:
    t = report.totals
    claims = [
        ClaimCheck(
            id=r.claim.id,
            statement=r.claim.statement,
            type=r.claim.type.value,
            verdict=r.verdict.value,
            path=r.path.value,
            source_url=r.source_url,
            quote=r.quote,
            reason=r.reason,
            source_sentence=r.claim.source_sentence,
        )
        for r in report.results
    ]
    notes = list(notes) + [f"Claim extraction: {e}" for e in report.extraction.errors]
    return CheckOutput(
        totals=Totals(claims=t.claims, supported=t.supported, contradicted=t.contradicted, unverifiable=t.unverifiable),
        claims=claims,
        models_used=models_used,
        notes=notes,
    )


def _short(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def summarize(out: CheckOutput) -> str:
    t = out.totals
    if not out.claims:
        lines = ["No checkable claims about third-party facts were found."]
    else:
        lines = [
            f"{t.claims} claim{'s' if t.claims != 1 else ''}: {t.supported} supported, "
            f"{t.contradicted} contradicted, {t.unverifiable} unverifiable."
        ]
        for c in out.claims:
            line = f"- {c.verdict.upper()} ({c.path}): {c.statement} {c.reason}".rstrip()
            if c.source_url:
                line += f" Source: {c.source_url}"
            if c.quote:
                line += f' Quote: "{_short(c.quote, MAX_SUMMARY_QUOTE)}"'
            lines.append(line)
    lines += [f"Note: {n}" for n in out.notes]
    return "\n".join(lines)


def run_check(text: str, context_factory: ContextFactory = default_context) -> CheckOutput:
    ctx, notes = context_factory()
    try:
        report = check(text, context=ctx)
    finally:
        ctx.close()
    return to_output(report, ctx.llm is not None, notes)


def _result(out: CheckOutput) -> CallToolResult:
    return CallToolResult(
        content=[TextContent(type="text", text=summarize(out))],
        structured_content=out.model_dump(mode="json"),
    )


def _error(message: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=message)], is_error=True)


READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=True)


def build_server(context_factory: ContextFactory = default_context) -> MCPServer:
    # WARNING keeps per-request HTTP logs (httpx logs every call at INFO) out of the client's stderr.
    server = MCPServer("hearsay", instructions=INSTRUCTIONS, version=__version__, log_level="WARNING")

    def _run(text: str) -> CallToolResult:
        if not text.strip():
            return _error("Give some text to check.")
        try:
            return _result(run_check(text, context_factory))
        except ConfigError as exc:
            return _error(f"Hearsay is not configured: {exc}")

    @server.tool(name="hearsay_check", title="Check the claims in a text", annotations=READ_ONLY)
    def hearsay_check(
        text: Annotated[str, Field(description="A pull request description, an answer or any text with claims.")],
    ) -> Annotated[CallToolResult, CheckOutput]:
        """Check every claim about third-party facts in a text against primary sources: package and version
        existence, CVE fix versions, licences, deprecations, documented parameters and vendor API behaviour.
        Returns a verdict per claim (supported, contradicted, unverifiable) with the source URL and a verbatim
        quote. Claims about the author's own work are skipped."""
        return _run(text)

    @server.tool(name="hearsay_claim", title="Check one statement", annotations=READ_ONLY)
    def hearsay_claim(
        sentence: Annotated[
            str, Field(description='One statement, for example "requests 2.31.0 fixes CVE-2023-32681".')
        ],
    ) -> Annotated[CallToolResult, CheckOutput]:
        """Check one statement about a package, advisory, licence or documented API before making it.
        Returns the verdict (supported, contradicted, unverifiable), what decided it, the source URL and a
        verbatim quote."""
        return _run(sentence)

    return server


def main() -> None:
    build_server().run("stdio")


if __name__ == "__main__":
    main()
