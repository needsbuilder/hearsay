# Hearsay benchmark: no-llm, extraction patterns

Run 2026-10-17T11:24:11 on 23 claims (dataset sha256 c35bea6196bf), hearsay 0.1.0.
No model calls (registry and advisory checks only).

| | n | correct | accuracy | abstained | wrong | overclaimed | decisive precision |
|---|---|---|---|---|---|---|---|
| **all** | 23 | 18 | 0.783 | 2 | 2 | 1 | 0.857 |
| label: contradicted | 11 | 9 | 0.818 | 2 | 0 | 0 | 1.0 |
| label: supported | 11 | 9 | 0.818 | 0 | 2 | 0 | 0.818 |
| label: unverifiable | 1 | 0 | 0.0 | 0 | 0 | 1 | 0.0 |
| route: advisory | 11 | 7 | 0.636 | 1 | 2 | 1 | 0.7 |
| route: registry | 12 | 11 | 0.917 | 1 | 0 | 0 | 1.0 |
| type: affected_by_vulnerability | 4 | 1 | 0.25 | 0 | 2 | 1 | 0.25 |
| type: deprecated | 2 | 1 | 0.5 | 1 | 0 | 0 | 1.0 |
| type: fixes_vulnerability | 7 | 6 | 0.857 | 1 | 0 | 0 | 1.0 |
| type: license_is | 3 | 3 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: package_exists | 3 | 3 | 1.0 | 0 | 0 | 0 | 1.0 |
| type: version_exists | 4 | 4 | 1.0 | 0 | 0 | 0 | 1.0 |
| path: advisory | 10 | 7 | 0.7 | 0 | 2 | 1 | 0.7 |
| path: none | 2 | 0 | 0.0 | 2 | 0 | 0 | None |
| path: registry | 11 | 11 | 1.0 | 0 | 0 | 0 | 1.0 |

Abstained: truth supported/contradicted, Hearsay unverifiable. Wrong: supported for contradicted or the reverse (the costly error). Overclaimed: a decisive verdict on a claim labelled unverifiable. Decisive precision: share of supported/contradicted verdicts that were right.

Confusion (rows: label, columns: Hearsay):

| label | supported | contradicted | unverifiable |
|---|---|---|---|
| contradicted | 0 | 9 | 2 |
| supported | 9 | 2 | 0 |
| unverifiable | 0 | 1 | 0 |

Cost this run: 0 Tavily calls (0 cached), 0 model calls (0 cached), 0 HTTP requests (43 cached). Tokens this run: none reported; replayed from cache: none reported.

Not correct:

- `r13` label supported, Hearsay contradicted (wrong, path advisory): lodash 4.17.21 is outside every affected range of CVE-2026-4800.
- `r16` label contradicted, Hearsay unverifiable (abstained, path none): OSV has no record CVE-2022-23529.
- `r21` label contradicted, Hearsay unverifiable (abstained, path none): Tavily is not configured (TAVILY_API_KEY).
- `r22` label supported, Hearsay contradicted (wrong, path advisory): urllib3 1.26.17 is outside every affected range of CVE-2023-43804.
- `u01` label unverifiable, Hearsay contradicted (overclaimed, path advisory): Werkzeug 1.0.1 is outside every affected range of CVE-2023-46136.
