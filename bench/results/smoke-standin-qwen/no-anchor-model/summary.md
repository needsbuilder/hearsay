# Hearsay benchmark: no-anchor, extraction model

Run 2026-10-17T11:21:48 on 3 claims (dataset sha256 c35bea6196bf), hearsay 0.1.0.
Models: base URL `http://localhost:11434/v1`, extractor `qwen2.5:7b`, judges `qwen2.5:3b, qwen2.5:7b`, adjudicator `qwen2.5:7b`.

**Not Nemotron on Token Factory: these model-stage numbers come from another endpoint (for example the local development stand-in) and are not a result.**

| | n | correct | accuracy | abstained | wrong | overclaimed | decisive precision |
|---|---|---|---|---|---|---|---|
| **all** | 3 | 2 | 0.667 | 1 | 0 | 0 | 1.0 |
| label: supported | 3 | 2 | 0.667 | 1 | 0 | 0 | 1.0 |
| route: docs | 3 | 2 | 0.667 | 1 | 0 | 0 | 1.0 |
| type: api_behavior | 1 | 1 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: deprecated | 1 | 1 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: other_external | 1 | 0 | 0.0 | 1 | 0 | 0 | None |
| path: jury | 3 | 2 | 0.667 | 1 | 0 | 0 | 1.0 |

Abstained: truth supported/contradicted, Hearsay unverifiable. Wrong: supported for contradicted or the reverse (the costly error). Overclaimed: a decisive verdict on a claim labelled unverifiable. Decisive precision: share of supported/contradicted verdicts that were right.

Confusion (rows: label, columns: Hearsay):

| label | supported | contradicted | unverifiable |
|---|---|---|---|
| supported | 2 | 0 | 1 |

Cost this run: 0 Tavily calls (6 cached), 4 model calls (5 cached), 0 HTTP requests (0 cached). Tokens this run: {'prompt_tokens': 5160, 'completion_tokens': 484, 'total_tokens': 5644, 'calls_with_usage': 4}; replayed from cache: {'prompt_tokens': 6049, 'completion_tokens': 462, 'total_tokens': 6511, 'calls_with_usage': 5}.

Not correct:

- `d26` label supported, Hearsay unverifiable (abstained, path jury): The judges found nothing in the passages that settles the claim.
