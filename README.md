# Hearsay

Coding agents state facts about the outside world in pull request descriptions, chat answers and code comments: "requests 2.31.0 fixes CVE-2023-32681", "the `timeout` parameter of `requests.get` is in the official docs", "this library is MIT licensed", "`datetime.utcnow()` is deprecated since Python 3.12". Hearsay extracts those claims and checks each one against a primary source. Every verdict carries the source URL and a verbatim quote. Without a primary source, the verdict is `unverifiable`.

The name: an agent's statement about the world is hearsay until a primary source backs it.

Hearsay is an entry for the NVIDIA x Nebius Global AI Hackathon (track: Coding and Agentic Engineering).

## Status

- The model stages (claim extraction and the jury) are built for **Nebius Token Factory** (OpenAI-compatible API, `https://api.tokenfactory.nebius.com/v1/`) with **NVIDIA Nemotron** models. **The Token Factory configuration is pending**: the API key has not been issued yet, so the model ids in `.env.example` are placeholders. They will be filled in from `GET /v1/models` once the key exists. The real jury uses distinct Nemotron models.
- Until then, the model stages were developed against a local OpenAI-compatible server (Ollama with `qwen2.5:7b` and `qwen2.5:3b`, see `dev/ollama.env`). This is a development stand-in only. The example outputs in `examples/` were produced with it, and the notes below say what it got right and wrong.
- The registry, advisory and Tavily paths are complete and were run against the live services.

## What it checks

| Claim type | Example | Decided by | Primary source |
|---|---|---|---|
| `package_exists` | "Added `pydantic-settings-extra`" | registry | PyPI JSON API, npm registry |
| `version_exists` | "`fastapi==0.200.0`" | registry | PyPI JSON API, npm registry |
| `fixes_vulnerability` | "requests 2.31.0 fixes CVE-2023-32681" | advisory | OSV |
| `affected_by_vulnerability` | "lodash 4.17.20 is affected by CVE-2021-23337" | advisory | OSV |
| `license_is` | "httpx is BSD-3-Clause licensed" | registry | deps.dev, then PyPI or npm metadata |
| `deprecated` | "the `left-pad` package is deprecated" | registry (npm `deprecated` field) | npm registry |
| `deprecated` | "`datetime.utcnow()` is deprecated since Python 3.12" | jury | official docs via Tavily |
| `parameter_exists` | "`requests.get` accepts a `timeout` parameter" | jury | official docs via Tavily |
| `api_behavior` | "Stripe refunds accept an idempotency key" | jury | official docs via Tavily |
| `other_external` | "GitHub Actions allows at most 256 jobs per workflow run in a matrix" | jury | official docs via Tavily |

Claims about the agent's own work ("tests pass", "I refactored X") are not Hearsay's job and are skipped.

## How a claim is decided

1. **Extract claims (model).** The input is split into numbered sentences. The extractor model returns atomic claims as JSON: a type, structured fields (package, version, vulnerability id, licence, symbol, parameter, since version, subject), a `negated` flag and the numbers of the sentences the claim came from. Hearsay attaches the source sentence itself, copied from the input, so it is always verbatim. Validation is strict:
   - unknown keys, unknown types and missing required fields are errors;
   - every package, version, vulnerability id, parameter, symbol and licence value must appear in the cited sentence (a claim that cites the wrong sentence number is moved to the one sentence that contains all its values, if there is exactly one);
   - for claims whose verdict Hearsay flips on negation, the `negated` flag must match the statement.
   One repair round is allowed: the model gets the errors and returns corrected versions of the invalid claims. Claims that are still invalid are dropped and listed in the report. Install commands and pins (`pip install x`, `pkg==1.2.3`, `pkg@1.2.3`, "Bumps pkg from A to B") that the model missed are added by pattern and marked `origin: pattern`.
2. **Registry and advisory claims: no model.** PyPI (`/pypi/<name>/json`), the npm registry (abbreviated metadata and per-version documents), OSV (`/v1/query`, `/v1/vulns/<id>`) and deps.dev (`/v3/systems/.../versions/...`) answer these deterministically.
   - Versions are compared with `packaging.version` (PEP 440) for PyPI and a SemVer 2.0.0 implementation for npm, including pre-release ordering.
   - OSV ranges are evaluated as the OSV schema describes: events sorted by version, `introduced` inclusive, `fixed` and `limit` exclusive, `last_affected` inclusive, several introduced/fixed pairs per range.
   - "X fixes CVE" is supported only if X is outside every affected range and at or after a fix; a version older than the bug is contradicted ("it never had the bug, so it does not contain the fix").
   - OSV merges aliases, so a later advisory can list an older CVE as an alias. The record whose own id was asked for decides, otherwise the earliest published one. Records that disagree are reported in the notes (real example: CVE-2021-23337 in lodash).
   - Licences: deps.dev's SPDX expression first, then `license_expression`, `license` and classifiers on PyPI, or `license` on npm. "BSD" claimed against "BSD-3-Clause" is supported; "BSD-3-Clause" claimed against the vague classifier "BSD License" is unverifiable; a licence that is only one part of an `AND` expression is unverifiable.
   - Each verdict carries the URL it came from and, as its quote, the exact field and value it relied on, for example `affected[requests].ranges.events: [{"introduced": "2.3.0"}, {"fixed": "2.31.0"}]`.
3. **Documentation claims: Tavily, scoped to the official docs.** For `parameter_exists`, `api_behavior`, `other_external` and `deprecated` (when no registry field answers it):
   - The official documentation domain comes from, in order: the Python standard library (`docs.python.org`), Node.js built-ins (`nodejs.org`) and JavaScript built-ins (`developer.mozilla.org`); a small curated map of vendors and languages (Stripe, GitHub, MDN, Node.js, TypeScript, React, Django, Go, Rust, PostgreSQL, Docker, Kubernetes, OpenAI, Tavily); the package's registry metadata (PyPI `project_urls` Documentation or Homepage, npm `homepage`).
   - A package whose only link is a code host (GitHub, GitLab) gets its repository page read directly, because restricting a search to `github.com` would let anyone's repository in.
   - Tavily Search runs with `include_domains` set to that domain. Tavily Extract then reads the top three results with the claim as its reranking `query`, so only the most relevant chunks of each page come back. Translated pages are skipped when English ones exist.
   - Hearsay splits those chunks into paragraphs, scores them by the claim's terms (identifiers weigh most) and keeps at most six passages and 4,500 characters for the jury.
   - No official domain found means no search and an `unverifiable` verdict. Hearsay does not fall back to the open web.
4. **The jury (documentation claims only).** Several judge models independently read the claim and the passages and return `supported`, `contradicted` or `unverifiable`, a verbatim quote and the URL. A quote that does not appear in the passages (after normalising Unicode, quotes, dashes, Markdown and whitespace), is shorter than 15 characters or skips text with an ellipsis turns that judge's verdict into `unverifiable`. The URL reported is the passage where the quote really is. If the judges agree, that is the verdict. If they disagree, an adjudicator model (a larger one) sees the claim, the passages and every judge's verdict, reasoning, quote and whether that quote was found, and decides under the same quote rule. A judge whose output stays invalid after one repair round counts as `unverifiable`.
5. **Report.** JSON for machines and Markdown for a pull request comment: totals at the top, then per claim the verdict, the source URL, the quote, the decision path, each judge's verdict for jury claims, notes, and optionally the evidence passages.

### Decision paths

| Path | Meaning |
|---|---|
| `registry` | PyPI, npm or deps.dev metadata decided it, no model |
| `advisory` | OSV advisory data decided it, no model |
| `jury` | documentation evidence, the judges agreed (after the quote rule) |
| `adjudicator` | documentation evidence, the judges disagreed and the adjudicator decided |
| `none` | nothing decided it: no official source, unsupported ecosystem, Tavily budget reached, lookup error, or `--no-llm` for a docs claim |

## Install and run

Requires Python 3.12 and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
cp .env.example .env    # fill in the Token Factory and Tavily settings

uv run hearsay check pr-description.md
uv run hearsay check --github-pr owner/repo#123          # public PR, unauthenticated GitHub API
uv run hearsay claim "requests 2.31.0 fixes CVE-2023-32681"
cat answer.md | uv run hearsay check --json              # stdin
uv run hearsay check pr-description.md --no-llm          # no model calls at all
```

Options (for `check` and `claim`):

| Option | Effect |
|---|---|
| `--json` / `--markdown` | print the JSON or the Markdown report (Markdown is the default) |
| `--json-out PATH`, `--md-out PATH` | also write the report to a file |
| `--evidence` | include the passages the jury read in the Markdown report |
| `--no-llm` | no model calls: a pattern extractor finds install commands, pins, "X fixes CVE-..." sentences, "licensed under" phrases and npm deprecations, and only registry and advisory checks run |
| `--env-file PATH` | load settings from a file (repeatable); `.env` in the working directory is loaded automatically |
| `--refresh` | ignore cached answers (they are fetched again and rewritten) |
| `--fail-on-contradicted` | exit with status 2 if any claim is contradicted |
| `-q` | no progress messages on stderr |

As a library:

```python
import hearsay

report = hearsay.check("Bumped requests to 2.31.0, which fixes CVE-2023-32681.")
print(report.totals)
print(hearsay.to_markdown(report))
```

`hearsay.check_claims([...])` checks claims that are already structured, and `hearsay.Context.create(...)` lets a caller share one cache, HTTP client and Tavily budget across calls.

## Configuration

| Variable | Meaning |
|---|---|
| `HEARSAY_LLM_BASE_URL` | OpenAI-compatible endpoint; default `https://api.tokenfactory.nebius.com/v1/` |
| `HEARSAY_LLM_API_KEY` | key for that endpoint |
| `HEARSAY_EXTRACT_MODEL` | model that extracts claims |
| `HEARSAY_JUDGE_MODELS` | judge models, comma separated (distinct Nemotron models in production) |
| `HEARSAY_ADJUDICATOR_MODEL` | larger model used only when judges disagree |
| `TAVILY_API_KEY` | Tavily key (sent as `Authorization: Bearer`, never stored or printed) |
| `HEARSAY_TAVILY_MAX_CALLS` | uncached Tavily calls allowed per run, default 20 |
| `HEARSAY_CACHE_DIR` | cache directory, default `.hearsay-cache`; `off` disables it |
| `HEARSAY_LLM_TIMEOUT` | seconds per model call, default 300 |

Values written as `<placeholder>` count as unset. Model calls use temperature 0 and JSON mode. Reasoning blocks (`<think>...</think>`) and code fences around the JSON are tolerated; the JSON itself is validated strictly.

## Cache and budget

Every HTTP, Tavily and model call goes through an on-disk cache keyed by the request (method, URL, parameters, body and the headers that change the answer; API keys are never part of the key or the stored file). A rerun of the same input costs nothing and produces the same report. Answers of 200 and 404 are cached; server errors are retried and not cached.

Tavily calls are counted per run. Cached calls are free; once `HEARSAY_TAVILY_MAX_CALLS` uncached calls have been made, further documentation claims become `unverifiable` with the reason. Every real Tavily call is appended to `.hearsay-cache/tavily-ledger.jsonl` (time, endpoint, query or URLs, no key).

## What Hearsay does not check

- Claims about the author's own code or process: tests passing, refactors, benchmarks it ran. That is a job for CI.
- Ecosystems other than PyPI and npm (crates.io, Maven, Go modules, RubyGems): such claims are `unverifiable`.
- Anything without an official documentation domain: Hearsay does not search the open web, blogs, Stack Overflow or other people's repositories.
- Opinions, popularity, performance numbers and plans ("most teams prefer httpx").
- Version-specific documentation: Tavily returns the current docs, so a claim about an old release may be judged against newer text.
- Licence files inside the package: licence checks use declared metadata.
- Whether a quote actually entails the verdict. The quote rule proves that the text exists in the source, not that it is about the claimed symbol (see Known problems).
- Private packages, private registries and private pull requests.

## Examples

`examples/` holds the inputs and the reports of real runs against live PyPI, npm, OSV, deps.dev, GitHub and Tavily, with the **local development stand-in** (qwen2.5:7b extractor, qwen2.5:3b and qwen2.5:7b judges, qwen2.5:7b adjudicator), not with Nemotron. The reports were last re-rendered from the cache, so their "Calls this run" lines show cache hits.

| Input | Report |
|---|---|
| `agent-pr.md`: an agent-style PR description with true, false, unverifiable and own-code claims | `agent-pr.report.md`, `.json` |
| `chat-answer.md`: an agent-style chat answer | `chat-answer.report.md`, `.json` |
| `gesiscss/gesis_surf_backend#67` (a public Dependabot PR), with `--no-llm` | `github-pr-dependabot.report.md`, `.json` |

What the stand-in got right and wrong (a handful of claims, not an accuracy measurement):

- **Registry and advisory claims (9 across the two inputs, plus 2 version claims in the Dependabot PR): all as expected.** Including: urllib3 1.26.5 does not fix CVE-2023-43804 (fixed in 1.26.17); `fastapi==0.200.0` does not exist; `pydantic-settings-extra` is on neither registry; requests is Apache-2.0, not MIT; lodash 4.17.21 is not affected by CVE-2021-23337 by the original advisory, with a note that a 2026 advisory aliased to the same CVE says otherwise.
- **Documentation claims (7): 5 as expected, 1 unverifiable, 1 wrong.**
  - As expected: `datetime.utcnow()` deprecated in 3.12 (supported), "distutils was removed in Python 3.10" (contradicted: removed in 3.12), Stripe idempotency keys (supported), the GitHub Actions 256-job matrix limit (supported), `Array.prototype.at()` with negative indexes (supported).
  - Unverifiable: "`requests.get` accepts a `max_retries` parameter". The claim is false, but the passages only describe `max_retries` on `HTTPAdapter`, so no quote settles it.
  - Wrong: "`fs.rm` supports a `recursive` option" came out **contradicted**. Two judges and the adjudicator quoted "v25.0.0 | Remove `recursive` option." from the version history of `fs.rmdir`, a different function. The quote is real, so the quote rule let it through.
- **Extraction:** the 7B extractor missed two claims in `agent-pr.md` (the documented `timeout` parameter and the GitHub Actions limit), and skipped the own-code claim and the opinion as intended. Before the validation rules above were added, it also set `negated` wrongly in both directions, cited a wrong sentence number, and typed the GitHub Actions sentence as `affected_by_vulnerability`.
- **Jury behaviour:** the 3B judge often quoted text that is not in the passages or quoted the claim itself; the quote rule turned those votes into `unverifiable`, which is why most documentation claims went to the adjudicator. Verdicts on the same claims also changed between prompt revisions, so these runs say little about prompt quality for Nemotron.

## Development

```sh
uv run pytest                              # 135 tests, no network, no model calls
uv run python tests/record_fixtures.py     # re-record fixtures (see below)
```

The suite replays real responses recorded in `tests/fixtures/cache` through a read-only cache, refuses any socket connection, and uses a scripted fake model. `tests/record_fixtures.py` records PyPI, npm, deps.dev, OSV and GitHub answers (trimmed to the fields Hearsay reads) and copies Tavily answers from the development cache with network access to Tavily blocked, so recording spends no Tavily credits.

Layout: `src/hearsay/` has `extract.py` (model extraction), `patterns.py` (no-model extraction), `registries.py`, `versions.py`, `licenses.py` and `deterministic.py` (registry and advisory checks), `docs_domain.py`, `tavily.py`, `passages.py`, `jury.py`, `quotes.py` and `docs.py` (documentation path), `pipeline.py` (routing), `report.py`, `cli.py`, `cache.py`, `http.py` and `llm.py`.

## Known problems

- **Quote relevance.** A verbatim quote can be about the wrong symbol (`fs.rmdir` for `fs.rm` above). Tavily's chunks lose the section heading that says which function a table belongs to.
- **Extraction recall** depends on the extractor model; the safety net only covers install commands and pins.
- **OSV alias merging** means "the advisory for this CVE" is a choice; Hearsay picks the matching or earliest record and reports disagreement rather than resolving it.
- **No ecosystem stated** and a package name that exists on both PyPI and npm makes version and licence claims `unverifiable`.

## License

MIT, see `LICENSE`.
