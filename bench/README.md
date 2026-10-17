# Hearsay benchmark

A small, hand-labelled set of claims of the kind coding agents write, used to measure how often Hearsay's verdict is right and whether the jury of judges beats a single judge.

**Status: the documentation results are pending Nemotron.** The model stages are built for NVIDIA Nemotron on Nebius Token Factory, and that key does not exist yet. The registry and advisory part needs no model and has been run (results below). The documentation part has only been smoke-tested on 3 claims with the local development stand-in (qwen2.5 on Ollama). That run checks the runner and is not a result.

## What the set contains

`claims.jsonl` has 64 claims, one JSON object per line. Each claim was labelled on 2026-10-17.

| Part | Claims | supported | contradicted | unverifiable |
|---|---|---|---|---|
| Registry and advisory (PyPI, npm, OSV, GitHub advisories, CVE.org, deps.dev) | 23 | 11 | 11 | 1 |
| Documentation (Python, Node.js, MDN, Stripe, GitHub, requests, httpx, pandas, NumPy, React, Express, OpenAI) | 41 | 17 | 20 | 4 |
| **All** | **64** | **28** | **31** | **5** |

By Hearsay claim type: `api_behavior` 16, `deprecated` 16 (2 of them npm package deprecations), `fixes_vulnerability` 7, `other_external` 6, `parameter_exists` 5, `affected_by_vulnerability` 4, `version_exists` 4, `license_is` 3, `package_exists` 3.

Fields:

| Field | Meaning |
|---|---|
| `id` | `r..` registry/advisory, `d..` documentation, `u..` genuinely unverifiable |
| `sentence` | one sentence, written the way an agent would write it in a PR description or chat answer |
| `type` | Hearsay's claim type for the fact the sentence states |
| `label` | `supported`, `contradicted` or `unverifiable`: the truth on 2026-10-17 |
| `route` | which part of Hearsay should decide it: `registry`, `advisory` or `docs` |
| `source_url` | the primary source that settles it (for unverifiable claims, the closest primary source that was checked, or null) |
| `source_quote` | verbatim text from that page, or for JSON APIs the field and value (`path: value`, several joined by `; `) |
| `notes` | why, and the trap if there is one |
| `claim` | the gold structured claim (Hearsay's fields: ecosystem, package, version, vulnerability_id, license, symbol, parameter, since_version, subject, negated), used by `--extraction gold` |

The set includes traps that Hearsay or its judges have hit before:

- **A similar function documented on the same page**: `fs.rm` vs `fs.rmdir` (d09, d10, d11), `fs.exists` vs `fs.existsSync` (d12, d13), `toSorted()` vs `sort()` (d20).
- **Removal vs deprecation, and the wrong version**: `distutils` removed in 3.10 (d03, it was deprecated then), `ssl.wrap_socket()` deprecated in 3.12 (d05, it was removed then), `DataFrame.append` deprecated in pandas 2.0 (d34), `np.float` first deprecated in 1.24 (d35), `datetime.utcnow()` deprecated since 3.10 (d02), Node's `fetch` stable since v18 (d14, only unflagged then).
- **A fix in a later patch than claimed**: urllib3 2.0.5 (r09, fixed in 2.0.6), Django 5.0.8 (r14, fixed in 5.0.9); a version older than the bug (r10).
- **Advisories with conflicting or merged records**: lodash CVE-2021-23337 and its 2026 incomplete-fix follow-up CVE-2026-4800, which OSV merges as aliases (r12, r13); Werkzeug CVE-2023-46136, where the GitHub-reviewed advisory, PYSEC and the maintainers' advisory disagree about old versions (u01); a withdrawn advisory with a rejected CVE (r16).
- **Registry edge cases**: an npm package that answers HTTP 200 but has only unpublished versions (r03), plausible versions that never existed (r05 `numpy==1.27.0`, r06 `react@18.4.0`), a negated sentence (r22).
- **Plausible parameters that do not exist**: `shutil.rmtree(force=...)` (d07), `requests.get(max_retries=...)` (d32).
- **Stale knowledge**: a pull request opened with `GITHUB_TOKEN` now creates approval-required workflow runs (d29).
- **Genuinely unverifiable** (u02 to u05): Stripe's storage backend for idempotency keys, GPT-4o's parameter count, a removal plan for `fs.exists()` that no source states, a popularity statistic.

## How the labels were made

Every label comes from reading the primary source, not from memory and not from search snippets:

- Registry and advisory claims: the PyPI JSON API, the npm registry, OSV (`/v1/vulns/<id>` and `/v1/query`), the GitHub advisory API, CVE.org and deps.dev, fetched with curl. The quote is the field and value the label rests on, for example `affected[urllib3].ranges.events: [{"introduced": "2.0.0"}, {"fixed": "2.0.6"}]`, or `HTTP 404: {"message": "Not Found"}` for something that does not exist.
- Documentation claims: the vendor's own pages, fetched with curl and read as text. Versioned pages were used where they exist: `docs.python.org/3.14`, `nodejs.org/docs/latest-v26.x`, release notes for pandas, NumPy, React and Express. Unversioned pages (MDN, Stripe, GitHub, httpx, requests `/en/latest/`, because no versioned requests URL answered) reflect 2026-10-17. The quote is copied verbatim.
- No Tavily calls were used for labelling.
- A claim was labelled `unverifiable` only when no public primary source settles it. Conflicting primary records count as unverifiable (u01).
- `--dry-run` re-checks every quote against its source: page quotes must appear in the page text (after Hearsay's normalisation of whitespace, quote marks and dashes), and JSON quotes must hold as `path: value` assertions in the API response.

Judgment calls, stated so they can be disputed:

- r16: "jsonwebtoken 9.0.0 fixes CVE-2022-23529" is labelled `contradicted`, because the CVE record is `REJECTED` ("The issue is not a vulnerability") and the advisory was withdrawn. `unverifiable` would be the conservative alternative, and scoring treats that answer as an abstention, not an error.
- d07 and d32: "a parameter that does not exist" is labelled `contradicted` because the documentation gives a complete parameter list: `shutil.rmtree` has a closed signature, and `requests.request` documents every keyword argument that `requests.get` passes on.
- r21: "the `express` npm package is deprecated" is `contradicted` because the version document of the latest release (5.3.0) has no `deprecated` field, which is how npm marks a deprecation.

Labels can go stale. Latest versions, licences of the latest release and unversioned documentation pages can change after 2026-10-17. `--dry-run` reads sources from the cache when it can; `--dry-run --live` fetches every source again, which is the check to run before a scored run on a later date.

## Scoring

Each sentence gets one verdict. With model or pattern extraction, a sentence can yield several claims. The verdict comes from the first extracted claim of the labelled type, otherwise from the only claim. A sentence with no claim counts as `unverifiable`. `results.jsonl` records how each verdict was chosen (`selection`) and every claim that was extracted.

| Outcome | Meaning |
|---|---|
| correct | the verdict equals the label |
| abstained | the label is supported or contradicted, Hearsay said unverifiable |
| wrong | supported when the truth is contradicted, or the reverse: the costly error |
| overclaimed | a supported or contradicted verdict on a claim labelled unverifiable |

`summary.json` and `summary.md` report accuracy overall, per label, per type, per route and per decision path, the confusion matrix, decisive precision (the share of supported or contradicted verdicts that were right), and cost: uncached and cached Tavily calls, model calls and HTTP requests, plus the tokens the API reported for fresh calls and for answers replayed from the cache. Claims that hit the Tavily budget or a lookup failure are listed under `infra_problems`, because that verdict is not Hearsay's judgement.

## How to run

From the `hearsay` directory, with the same settings as the CLI (`.env` is loaded automatically, and `--env-file` adds files; the first value wins):

```sh
uv run python bench/run.py --dry-run                         # validate fields, labels, URLs and quotes; no model or Tavily calls
uv run python bench/run.py --no-llm --part registry          # Hearsay's --no-llm path (pattern extraction), registry and advisory
uv run python bench/run.py --no-llm --extraction gold --part registry   # the same checks on the gold claims

uv run python bench/run.py --config jury                     # Hearsay as configured: extractor, judges, adjudicator
uv run python bench/run.py --config single                   # one judge, no adjudicator
uv run python bench/run.py --config no-anchor                # the jury with anchoring disabled (passage ranking and vote rule)
uv run python bench/run.py --config jury --extraction gold   # skip extraction: judge the gold claims
```

Options: `--part registry|docs`, `--ids d01,d16`, `--limit N`, `--env-file PATH`, `--tavily-max-calls N`, `--out DIR` (default `bench/results/<config>-<extraction>[-<part>]`), and for the dry run `--offline` (cache only) or `--live` (fetch every source again).

Model ids come from the environment, the same as Hearsay: `HEARSAY_EXTRACT_MODEL`, `HEARSAY_JUDGE_MODELS`, `HEARSAY_ADJUDICATOR_MODEL`. `single` uses `--single-model`, else `HEARSAY_BENCH_SINGLE_MODEL`, else the first judge. To ask whether the jury beats a single judge, run `single` once per judge model and once with the adjudicator model. Extraction, Tavily answers and identical judge calls are cached, so only the new calls cost anything.

Cost of a cold documentation run: about 2 Tavily calls per documentation claim (one search, one extract of the top 3 pages), so about 80 for the 41 documentation claims. Raise `--tavily-max-calls` (the default is 20 per run), otherwise later claims are reported under `infra_problems`. `single` and `no-anchor` reuse the Tavily answers and the extraction from the cache. Every call goes through Hearsay's cache (`.hearsay-cache`, or `HEARSAY_CACHE_DIR`), so rerunning a configuration is free and gives the same numbers.

## Results so far

### Registry and advisory part (deterministic, no model), 2026-10-17

`results/no-llm-patterns-registry/` is Hearsay's `--no-llm` path end to end, with the pattern extractor. `results/no-llm-gold-registry/` runs the same checkers on the gold claims.

| Run | n | correct | abstained | wrong | overclaimed |
|---|---|---|---|---|---|
| `--no-llm`, pattern extraction | 23 | 18 (78%) | 2 | 2 | 1 |
| `--no-llm`, gold claims | 23 | 19 (83%) | 2 | 1 | 1 |

Every verdict that came from registry metadata was right (11 of 11: the package, version and licence claims and the npm deprecation r20). The errors are in the advisory path and in extraction:

- **r13, wrong in both runs (bug).** "lodash 4.17.21 ... is still affected by CVE-2026-4800" is true: the advisory for CVE-2026-4800 (GHSA-r5fr-rjxr-66jc) covers `>= 4.0.0, <= 4.17.23`, fixed in 4.18.0. Hearsay answered contradicted. OSV merges aliases, so the 2021 advisory GHSA-35jh-r3h4-6jhm (CVE-2021-23337, fixed in 4.17.21) also lists CVE-2026-4800. No record's own id is the CVE, so `_rank_records` in `deterministic.py` falls back to the earliest published record, which is the 2021 advisory. The note reports the conflict, but the verdict is decisive and wrong. A record published years before a CVE id was issued cannot be that CVE's advisory.
- **r22, wrong with pattern extraction (bug).** "urllib3 1.26.17 in requirements.txt is not affected by CVE-2023-43804" is true. The `--no-llm` pattern extractor (`patterns.py`) matches "affected" and builds a positive `affected_by_vulnerability` claim with `negated=false`, so Hearsay answered contradicted. With the gold claim (`negated=true`) the checker is right. The extractor never sets `negated`, so "does not fix" and "is not affected" sentences are flipped.
- **u01, overclaimed in both runs.** Werkzeug 1.0.1 and CVE-2023-46136: the GitHub-reviewed record starts the range at 2.0.0rc1, while PYSEC-2023-221 and the maintainers' advisory include 1.0.1. Hearsay follows the GitHub record and answers contradicted, with the disagreement in a note. This is the documented design ("picks the matching or earliest record and reports disagreement"), but on disputed records it produces a confident verdict.
- Abstentions: r16 (rejected CVE; OSV has no record, so Hearsay says unverifiable: acceptable) and r21 (npm's metadata shows that express is not deprecated, but the registry check only confirms deprecations, so the claim goes to the documentation path, which `--no-llm` skips).

### Documentation part

Pending Nemotron on Token Factory.

`results/smoke-standin-qwen/` holds a runner check on 3 documentation claims (d01, d16, d26) under `jury`, `single`, `no-anchor` and `jury --extraction gold`, with the **local stand-in** (qwen2.5:7b extractor, qwen2.5:3b and qwen2.5:7b judges, qwen2.5:7b adjudicator on Ollama). It shows that the configurations, the cache reuse and the token accounting work. It is not a measurement of Hearsay, and its summaries say so.

## Limits

- 64 claims and one annotator. A difference of one or two claims between configurations is noise.
- The label is the truth of the sentence; Hearsay's documentation answers come from the current pages Tavily returns, so a claim about an old release can be judged against newer text (a known Hearsay limit).
- The gold claims fix the symbol, so they measure the jury without extraction errors. Model extraction measures the whole pipeline. Report both.
- The registry part's labels depend on the latest releases on 2026-10-17 (r01, r17 to r21).
