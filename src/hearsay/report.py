"""Render a Report as JSON (machines) or Markdown (a pull request comment)."""

from __future__ import annotations

from .models import ClaimResult, Report, Verdict

LABEL = {
    Verdict.SUPPORTED: "SUPPORTED",
    Verdict.CONTRADICTED: "CONTRADICTED",
    Verdict.UNVERIFIABLE: "UNVERIFIABLE",
}


def to_json(report: Report) -> str:
    return report.model_dump_json(indent=2)


def _cell(text: str | None, limit: int = 140) -> str:
    t = " ".join((text or "").split()).replace("|", "\\|")
    return t if len(t) <= limit else t[: limit - 3] + "..."


def _blockquote(text: str) -> str:
    return "\n".join("> " + line for line in " ".join(text.split()).splitlines())


def _source(r: ClaimResult) -> str:
    if r.source_url:
        return f"<{r.source_url}>"
    return "-"


def to_markdown(report: Report, *, include_evidence: bool = False) -> str:
    t = report.totals
    out = ["## Hearsay: claims about the outside world", ""]
    if report.input_title or report.input_url:
        out.append(f"Input: {report.input_title or ''} {f'<{report.input_url}>' if report.input_url else ''}".strip())
        out.append("")
    out.append(
        f"**{t.claims} claims checked: {t.supported} supported, {t.contradicted} contradicted, "
        f"{t.unverifiable} unverifiable.**"
    )
    out.append("")
    if not report.results:
        out.append("No checkable claims about third-party facts were found.")
    else:
        out.append("| # | Verdict | Claim | Decided by | Source |")
        out.append("|---|---|---|---|---|")
        for r in report.results:
            out.append(
                f"| {r.claim.id} | **{LABEL[r.verdict]}** | {_cell(r.claim.statement)} | {r.path.value} | {_cell(_source(r), 200)} |"
            )
        out.append("")
        for r in report.results:
            out.extend(_detail(r, include_evidence))

    ex = report.extraction
    out.append("---")
    if ex.method == "llm":
        extracted = f"Claims extracted by `{ex.model}` from {ex.sentences} sentences"
    else:
        extracted = f"Claims extracted by {ex.method} ({ex.sentences} sentences)"
    if ex.rejected:
        extracted += f"; {len(ex.rejected)} invalid extractions dropped"
    out.append(extracted + ".")
    if report.models.judge_models:
        out.append(
            f"Jury: {', '.join(f'`{m}`' for m in report.models.judge_models)}; "
            f"adjudicator `{report.models.adjudicator_model}`."
        )
    u = report.usage
    out.append(
        f"Calls this run: {u.http_requests} HTTP ({u.http_cache_hits} cached), "
        f"{u.tavily_calls} Tavily ({u.tavily_cache_hits} cached), {u.llm_calls} model ({u.llm_cache_hits} cached)."
    )
    out.append("")
    return "\n".join(out)


def _detail(r: ClaimResult, include_evidence: bool) -> list[str]:
    c = r.claim
    lines = [f"### {c.id}. {LABEL[r.verdict]}: {_cell(c.statement, 200)}", ""]
    lines.append(f"Claim type `{c.type.value}`, decided by **{r.path.value}**.")
    lines.append("")
    lines.append("Said in the input:")
    lines.append(_blockquote(c.source_sentence))
    lines.append("")
    lines.append(r.reason)
    lines.append("")
    if r.quote:
        lines.append(f"Source: <{r.source_url}>" if r.source_url else "Source: -")
        lines.append("")
        lines.append(_blockquote(r.quote))
        lines.append("")
    if r.judges:
        lines.append("| Judge | Model | Verdict | Stated | Quote found | Anchored |")
        lines.append("|---|---|---|---|---|---|")
        votes = list(r.judges) + ([r.adjudicator] if r.adjudicator else [])
        for i, v in enumerate(votes, 1):
            who = "adjudicator" if v.role == "adjudicator" else f"judge {i}"
            stated = v.stated_verdict.value if v.stated_verdict else "invalid output"
            anchored = "-" if v.anchored is None else ("yes" if v.anchored else "no")
            lines.append(
                f"| {who} | `{v.model}` | {v.verdict.value} | {stated} | {'yes' if v.quote_found else 'no'} | {anchored} |"
            )
        lines.append("")
        for i, v in enumerate(votes, 1):
            if v.error:
                who = "adjudicator" if v.role == "adjudicator" else f"judge {i}"
                lines.append(f"- {who}: {v.error}")
        if any(v.error for v in votes):
            lines.append("")
    if r.docs_domains:
        lines.append(f"Documentation searched: {', '.join(r.docs_domains)}.")
        lines.append("")
    for note in r.notes:
        lines.append(f"- {note}")
    if r.notes:
        lines.append("")
    if include_evidence and r.evidence:
        lines.append("<details><summary>Evidence shown to the jury</summary>")
        lines.append("")
        for p in r.evidence:
            lines.append(f"[{p.id}] <{p.url}>" + (f" ({_cell(' > '.join(p.section), 200)})" if p.section else ""))
            lines.append("")
            lines.append(_blockquote(p.text))
            lines.append("")
        lines.append("</details>")
        lines.append("")
    return lines
