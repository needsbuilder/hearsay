# Hearsay benchmark: jury, extraction gold

Run 2026-10-17T11:22:21 on 3 claims (dataset sha256 c35bea6196bf), hearsay 0.1.0.
Models: base URL `http://localhost:11434/v1`, extractor `None`, judges `qwen2.5:3b, qwen2.5:7b`, adjudicator `qwen2.5:7b`.

**Not Nemotron on Token Factory: these model-stage numbers come from another endpoint (for example the local development stand-in) and are not a result.**

| | n | correct | accuracy | abstained | wrong | overclaimed | decisive precision |
|---|---|---|---|---|---|---|---|
| **all** | 3 | 3 | 1.0 | 0 | 0 | 0 | 1.0 |
| label: supported | 3 | 3 | 1.0 | 0 | 0 | 0 | 1.0 |
| route: docs | 3 | 3 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: api_behavior | 1 | 1 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: deprecated | 1 | 1 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: other_external | 1 | 1 | 1.0 | 0 | 0 | 0 | 1.0 |
| path: adjudicator | 1 | 1 | 1.0 | 0 | 0 | 0 | 1.0 |
| path: jury | 2 | 2 | 1.0 | 0 | 0 | 0 | 1.0 |

Abstained: truth supported/contradicted, Hearsay unverifiable. Wrong: supported for contradicted or the reverse (the costly error). Overclaimed: a decisive verdict on a claim labelled unverifiable. Decisive precision: share of supported/contradicted verdicts that were right.

Confusion (rows: label, columns: Hearsay):

| label | supported | contradicted | unverifiable |
|---|---|---|---|
| supported | 3 | 0 | 0 |

Cost this run: 0 Tavily calls (6 cached), 6 model calls (2 cached), 0 HTTP requests (0 cached). Tokens this run: {'prompt_tokens': 6173, 'completion_tokens': 578, 'total_tokens': 6751, 'calls_with_usage': 6}; replayed from cache: {'prompt_tokens': 3160, 'completion_tokens': 246, 'total_tokens': 3406, 'calls_with_usage': 2}.
