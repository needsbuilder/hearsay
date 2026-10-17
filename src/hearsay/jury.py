"""The jury: several judge models read the same documentation passages
independently; an adjudicator decides only when they disagree.

A verdict of supported or contradicted counts only with a quote that appears
verbatim in the passages; otherwise it becomes unverifiable.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, field_validator

from .anchoring import Anchor
from .llm import ChatModel, LLMError, ask_json
from .models import Claim, DecisionPath, JudgeVote, Passage, Verdict
from .passages import claim_terms, score
from .quotes import display_quote, find_quote_all

RULES = """Verdicts:
- "supported": an excerpt states the claim, in substance, for the same function, option or API.
- "contradicted": an excerpt states something that cannot be true together with the claim: the same event with a different version, a different kind of change (deprecated is not removed), the feature said not to exist or to be removed, or a complete parameter list that leaves the parameter out.
- "unverifiable": the excerpts do not settle it. Choose this when in doubt. Do not use outside knowledge.

Each excerpt shows the section of the page it comes from. Use an excerpt only if its section is about the claim's function, option or API: an excerpt from the section of a different function (for example fs.rmdir when the claim is about fs.rm) does not count.

Before deciding, compare every detail of the claim with the excerpt: the exact name, every version number, and the kind of change. A claim is supported only if all of its details match.

Return a JSON object with exactly these keys:
{"reasoning": "<one or two sentences comparing the claim's details with the excerpt>", "verdict": "supported" | "contradicted" | "unverifiable", "url": "<URL of the excerpt you quote, or null>", "quote": "<text copied from that excerpt, or an empty string>"}

The quote must be copied character for character from one excerpt (never from the claim): one contiguous span of 15 to 300 characters, no ellipsis, no paraphrase. A supported or contradicted verdict without such a quote is discarded."""

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
    url: str | None = None
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
    # The source sentence is left out on purpose: models tend to quote it back.
    lines = [f"CLAIM: {claim.statement}"]
    if fields:
        lines.append("Details: " + "; ".join(fields))
    return "\n".join(lines)


def _evidence_block(passages: list[Passage]) -> str:
    blocks = []
    for p in passages:
        section = f"Section: {' > '.join(p.section)}\n" if p.section else ""
        blocks.append(f"[{p.id}] {p.url}\n{section}{p.text}")
    return "\n\n".join(blocks)


def judge_messages(claim: Claim, passages: list[Passage]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": f"{_claim_block(claim)}\n\nEXCERPTS:\n{_evidence_block(passages)}"},
    ]


def adjudicator_messages(claim: Claim, passages: list[Passage], votes: list[JudgeVote]) -> list[dict[str, str]]:
    lines = []
    for i, v in enumerate(votes, 1):
        said = v.stated_verdict.value if v.stated_verdict else "no valid answer"
        if v.quote_found and v.anchored is False:
            found = "found, but in a section about something else"
        else:
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
    llm: ChatModel,
    model: str,
    role: str,
    messages: list[dict[str, str]],
    passages: list[Passage],
    anchor: Anchor | None = None,
) -> JudgeVote:
    """One judge's vote, after the quote rule and the anchoring rule."""
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
    decisive = out.verdict != Verdict.UNVERIFIABLE
    if not vote.quote:
        if decisive:
            vote.verdict = Verdict.UNVERIFIABLE
            vote.error = f"no quote; the {out.verdict.value} verdict was discarded"
        return vote

    # Quote rule: the quote must be in the passages.
    named = [p.id for p in passages if out.url and p.url.rstrip("/") == out.url.strip().rstrip("/")]
    found, problem = find_quote_all(vote.quote, passages, named[0] if named else None)
    if not found:
        if decisive:
            vote.verdict = Verdict.UNVERIFIABLE
            vote.error = f"{problem}; the {out.verdict.value} verdict was discarded"
        return vote
    vote.quote_found = True

    # Anchoring rule: the passage holding the quote must be about the claim's symbol.
    passage = found[0]
    if anchor is not None and decisive:
        problems = [(p, anchor.problem(p)) for p in found]
        anchored = [p for p, prob in problems if prob is None]
        vote.anchored = bool(anchored)
        if anchored:
            passage = anchored[0]
        else:
            vote.verdict = Verdict.UNVERIFIABLE
            vote.error = f"anchoring: {problems[0][1]}; the {out.verdict.value} verdict was discarded"
    vote.url = passage.url  # where the quote really is, whatever URL the model named
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
    llm: ChatModel,
    judges: list[str],
    adjudicator: str,
    claim: Claim,
    passages: list[Passage],
    anchor: Anchor | None = None,
) -> JuryOutcome:
    messages = judge_messages(claim, passages)
    votes = [run_judge(llm, m, "judge", messages, passages, anchor) for m in judges]
    verdicts = {v.verdict for v in votes}

    if len(verdicts) == 1:
        verdict = votes[0].verdict
        valid = [v for v in votes if v.quote_found and v.anchored is not False and v.verdict == verdict]
        terms = claim_terms(claim)
        # The most relevant valid quote backs the verdict (ties: the longer one).
        backing = max(valid, key=lambda v: (score(v.quote or "", terms), len(v.quote or ""))) if valid else None
        if verdict == Verdict.UNVERIFIABLE:
            discarded = [v for v in votes if v.stated_verdict not in (None, Verdict.UNVERIFIABLE)]
            reason = "The judges found nothing in the passages that settles the claim."
            if discarded:
                said = "/".join(sorted({v.stated_verdict.value for v in discarded if v.stated_verdict}))
                why = (
                    "their quotes came from sections about something else"
                    if all(v.anchored is False for v in discarded)
                    else "their quotes were not in the evidence or not about the claim's symbol"
                    if any(v.anchored is False for v in discarded)
                    else "their quotes were not in the evidence"
                )
                reason = f"{len(discarded)} of {len(votes)} judges answered {said} but {why}, so the verdict is unverifiable."
            return JuryOutcome(verdict, DecisionPath.JURY, votes, reason=reason)
        assert backing is not None
        return JuryOutcome(
            verdict,
            DecisionPath.JURY,
            votes,
            quote=display_quote(backing.quote),
            url=backing.url,
            reason=f"All {len(votes)} judges agree. {backing.reasoning}".strip(),
        )

    adj = run_judge(llm, adjudicator, "adjudicator", adjudicator_messages(claim, passages, votes), passages, anchor)
    decisive = adj.quote_found and adj.verdict != Verdict.UNVERIFIABLE
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
        quote=display_quote(adj.quote) if decisive else None,
        url=adj.url if decisive else None,
        reason=reason,
    )
