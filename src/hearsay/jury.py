"""The jury: several judge models read the same documentation passages
independently; an adjudicator decides only when they disagree.

A verdict of supported or contradicted counts only with a quote that appears
verbatim in the passages; otherwise it becomes unverifiable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, field_validator

from .llm import ChatModel, LLMError, ask_json
from .models import Claim, DecisionPath, JudgeVote, Passage, Verdict
from .quotes import find_quote

RULES = """Verdicts:
- "supported": an excerpt states the claim, in substance, for the same function, option or API.
- "contradicted": an excerpt states something that cannot be true together with the claim (for example a different version, the feature is said not to exist or to have been removed, or a complete parameter list that leaves the parameter out).
- "unverifiable": the excerpts do not settle it. Choose this when in doubt. Do not use outside knowledge.

Return a JSON object with exactly these keys:
{"reasoning": "<one or two sentences>", "verdict": "supported" | "contradicted" | "unverifiable", "passage": <excerpt number or null>, "quote": "<text copied from that excerpt, or an empty string>"}

The quote must be copied character for character from one excerpt: one contiguous span of 15 to 300 characters, no ellipsis, no paraphrase. A supported or contradicted verdict without such a quote is discarded."""

JUDGE_SYSTEM = (
    "You check one claim about software against excerpts from its official documentation.\n\n" + RULES
)

ADJUDICATOR_SYSTEM = (
    "You check one claim about software against excerpts from its official documentation. "
    "Other judges read the same excerpts and disagreed; their answers are listed after the excerpts. "
    "They may be wrong, and a judge whose quote was not found in the excerpts made it up. "
    "Decide from the excerpts yourself.\n\n" + RULES
)


class JudgeOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reasoning: str = ""
    verdict: Verdict
    passage: int | None = None
    quote: str | None = ""

    @field_validator("verdict", mode="before")
    @classmethod
    def _lower(cls, v: object) -> object:
        return v.strip().lower() if isinstance(v, str) else v


def _claim_block(claim: Claim) -> str:
    fields = [
        f"{name}: {getattr(claim, name)}"
        for name in ("subject", "package", "symbol", "parameter", "version", "since_version")
        if getattr(claim, name)
    ]
    lines = [f"CLAIM: {claim.statement}", f'Sentence it came from: "{claim.source_sentence}"']
    if fields:
        lines.append("Details: " + "; ".join(fields))
    return "\n".join(lines)


def _evidence_block(passages: list[Passage]) -> str:
    return "\n\n".join(f"[{p.id}] {p.url}\n{p.text}" for p in passages)


def judge_messages(claim: Claim, passages: list[Passage]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": f"{_claim_block(claim)}\n\nEXCERPTS:\n{_evidence_block(passages)}"},
    ]


def adjudicator_messages(claim: Claim, passages: list[Passage], votes: list[JudgeVote]) -> list[dict[str, str]]:
    lines = []
    for i, v in enumerate(votes, 1):
        said = v.stated_verdict.value if v.stated_verdict else "no valid answer"
        found = "found in the excerpts" if v.quote_found else "NOT found in the excerpts"
        quote = f'quote ({found}): "{v.quote}"' if v.quote else "no quote"
        lines.append(f"Judge {i}: {said}. Reasoning: {v.reasoning or v.error or '-'} {quote}")
    return [
        {"role": "system", "content": ADJUDICATOR_SYSTEM},
        {
            "role": "user",
            "content": f"{_claim_block(claim)}\n\nEXCERPTS:\n{_evidence_block(passages)}\n\nJUDGES:\n" + "\n".join(lines),
        },
    ]


def run_judge(
    llm: ChatModel, model: str, role: str, messages: list[dict[str, str]], passages: list[Passage]
) -> JudgeVote:
    try:
        out, errors = ask_json(llm, model, messages, JudgeOutput.model_validate)
    except LLMError as exc:
        return JudgeVote(model=model, role=role, verdict=Verdict.UNVERIFIABLE, error=str(exc))
    if out is None:
        return JudgeVote(
            model=model, role=role, verdict=Verdict.UNVERIFIABLE, error="invalid output: " + " | ".join(errors)
        )
    vote = JudgeVote(
        model=model,
        role=role,
        verdict=out.verdict,
        stated_verdict=out.verdict,
        quote=(out.quote or "").strip() or None,
        reasoning=out.reasoning.strip(),
    )
    if vote.quote:
        passage, problem = find_quote(vote.quote, passages, out.passage)
        if passage is not None:
            vote.quote_found = True
            vote.url = passage.url
        elif out.verdict != Verdict.UNVERIFIABLE:
            vote.verdict = Verdict.UNVERIFIABLE
            vote.error = f"{problem}; the {out.verdict.value} verdict was discarded"
    elif out.verdict != Verdict.UNVERIFIABLE:
        vote.verdict = Verdict.UNVERIFIABLE
        vote.error = f"no quote; the {out.verdict.value} verdict was discarded"
    return vote


@dataclass
class JuryOutcome:
    verdict: Verdict
    path: DecisionPath
    votes: list[JudgeVote]
    adjudicator: JudgeVote | None = None
    quote: str | None = None
    url: str | None = None
    reason: str = ""
    notes: list[str] = field(default_factory=list)


def _summary(votes: list[JudgeVote]) -> str:
    return ", ".join(f"{v.model}: {v.verdict.value}" for v in votes)


def run_jury(
    llm: ChatModel, judges: list[str], adjudicator: str, claim: Claim, passages: list[Passage]
) -> JuryOutcome:
    messages = judge_messages(claim, passages)
    votes = [run_judge(llm, m, "judge", messages, passages) for m in judges]
    verdicts = {v.verdict for v in votes}

    if len(verdicts) == 1:
        verdict = votes[0].verdict
        backing = next((v for v in votes if v.quote_found and v.verdict == verdict), None)
        if verdict == Verdict.UNVERIFIABLE:
            discarded = [v for v in votes if v.stated_verdict not in (None, Verdict.UNVERIFIABLE)]
            reason = "The judges found nothing in the passages that settles the claim."
            if discarded:
                reason = (
                    f"{len(discarded)} of {len(votes)} judges answered "
                    + "/".join(sorted({v.stated_verdict.value for v in discarded if v.stated_verdict}))
                    + " but their quotes were not in the evidence, so the verdict is unverifiable."
                )
            return JuryOutcome(verdict, DecisionPath.JURY, votes, reason=reason)
        assert backing is not None
        return JuryOutcome(
            verdict,
            DecisionPath.JURY,
            votes,
            quote=backing.quote,
            url=backing.url,
            reason=f"All {len(votes)} judges agree. {backing.reasoning}".strip(),
        )

    adj = run_judge(llm, adjudicator, "adjudicator", adjudicator_messages(claim, passages, votes), passages)
    reason = f"Judges disagreed ({_summary(votes)}); the adjudicator decided {adj.verdict.value}."
    if adj.reasoning:
        reason += f" {adj.reasoning}"
    if adj.error:
        reason += f" ({adj.error})"
    return JuryOutcome(
        adj.verdict,
        DecisionPath.ADJUDICATOR,
        votes,
        adjudicator=adj,
        quote=adj.quote if adj.quote_found else None,
        url=adj.url if adj.quote_found else None,
        reason=reason,
    )
