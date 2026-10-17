# Hearsay benchmark: no-llm, extraction patterns

Run 2026-10-17T11:37:43 on 23 claims (dataset sha256 c35bea6196bf), hearsay 0.1.0.
No model calls (registry and advisory checks only).

| | n | correct | accuracy | abstained | wrong | overclaimed | decisive precision |
|---|---|---|---|---|---|---|---|
| **all** | 23 | 21 | 0.913 | 2 | 0 | 0 | 1.0 |
| label: contradicted | 11 | 9 | 0.818 | 2 | 0 | 0 | 1.0 |
| label: supported | 11 | 11 | 1.0 | 0 | 0 | 0 | 1.0 |
| label: unverifiable | 1 | 1 | 1.0 | 0 | 0 | 0 | None |
| route: advisory | 11 | 10 | 0.909 | 1 | 0 | 0 | 1.0 |
| route: registry | 12 | 11 | 0.917 | 1 | 0 | 0 | 1.0 |
| type: affected_by_vulnerability | 4 | 4 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: deprecated | 2 | 1 | 0.5 | 1 | 0 | 0 | 1.0 |
| type: fixes_vulnerability | 7 | 6 | 0.857 | 1 | 0 | 0 | 1.0 |
| type: license_is | 3 | 3 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: package_exists | 3 | 3 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: version_exists | 4 | 4 | 1.0 | 0 | 0 | 0 | 1.0 |
| path: advisory | 10 | 10 | 1.0 | 0 | 0 | 0 | 1.0 |
| path: none | 2 | 0 | 0.0 | 2 | 0 | 0 | None |
| path: registry | 11 | 11 | 1.0 | 0 | 0 | 0 | 1.0 |

Abstained: truth supported/contradicted, Hearsay unverifiable. Wrong: supported for contradicted or the reverse (the costly error). Overclaimed: a decisive verdict on a claim labelled unverifiable. Decisive precision: share of supported/contradicted verdicts that were right.

Confusion (rows: label, columns: Hearsay):

| label | supported | contradicted | unverifiable |
|---|---|---|---|
| contradicted | 0 | 9 | 2 |
| supported | 11 | 0 | 0 |
| unverifiable | 0 | 0 | 1 |

Cost this run: 0 Tavily calls (0 cached), 0 model calls (0 cached), 6 HTTP requests (47 cached). Tokens this run: none reported; replayed from cache: none reported.

Not correct:

- `r16` label contradicted, Hearsay unverifiable (abstained, path none): OSV has no record CVE-2022-23529.
- `r21` label contradicted, Hearsay unverifiable (abstained, path none): Tavily is not configured (TAVILY_API_KEY).
