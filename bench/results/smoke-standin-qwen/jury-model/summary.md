# Hearsay benchmark: jury, extraction model

Run 2026-10-17T11:21:15 on 3 claims (dataset sha256 c35bea6196bf), hearsay 0.1.0.
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
| path: adjudicator | 1 | 1 | 1.0 | 0 | 0 | 0 | 1.0 |
| path: jury | 2 | 1 | 0.5 | 1 | 0 | 0 | 1.0 |

Abstained: truth supported/contradicted, Hearsay unverifiable. Wrong: supported for contradicted or the reverse (the costly error). Overclaimed: a decisive verdict on a claim labelled unverifiable. Decisive precision: share of supported/contradicted verdicts that were right.

Confusion (rows: label, columns: Hearsay):

| label | supported | contradicted | unverifiable |
|---|---|---|---|
| supported | 2 | 0 | 1 |

Cost this run: 2 Tavily calls (4 cached), 7 model calls (4 cached), 0 HTTP requests (0 cached). Tokens this run: {'prompt_tokens': 8915, 'completion_tokens': 807, 'total_tokens': 9722, 'calls_with_usage': 7}; replayed from cache: {'prompt_tokens': 3859, 'completion_tokens': 317, 'total_tokens': 4176, 'calls_with_usage': 4}.

Not correct:

- `d26` label supported, Hearsay unverifiable (abstained, path jury): The judges found nothing in the passages that settles the claim.
