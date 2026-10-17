# Hearsay

Coding agents state facts about the outside world in pull request descriptions, chat answers and code comments: "requests 2.31.0 fixes CVE-2023-32681", "the `timeout` parameter of `requests.get` is in the official docs", "this library is MIT licensed", "`datetime.utcnow()` is deprecated since Python 3.12". Hearsay extracts those claims and checks each one against a primary source. Every verdict carries the source URL and a verbatim quote. Without a primary source, the verdict is `unverifiable`.

The name: an agent's statement about the world is hearsay until a primary source backs it.

Hearsay is an entry for the NVIDIA x Nebius Global AI Hackathon (track: Coding and Agentic Engineering).

## Status

- The model stages (claim extraction and the jury) are built for **Nebius Token Factory** (OpenAI-compatible API, `https://api.tokenfactory.nebius.com/v1/`) with **NVIDIA Nemotron** models. **The Token Factory configuration is pending**: the API key has not been issued yet, so the model ids in `.env.example` are placeholders. They will be filled in from `GET /v1/models` once the key exists. The real jury uses distinct Nemotron models.
- Until then, the model stages were developed against a local OpenAI-compatible server (Ollama with `qwen2.5:7b` and `qwen2.5:3b`, see `dev/ollama.env`). This is a development stand-in only. The example outputs in `examples/` were produced with it, and the notes below say what it got right and wrong.
- The registry, advisory and Tavily paths are complete and were run against the live services.
- Delivery: a web demo with a JSON API, an MCP server for coding agents, a GitHub Action, and Docker and Render files for the demo. The demo runs at https://hearsay-w4na.onrender.com (a free instance: the first request after it has been idle can take about a minute). Until the Token Factory settings are added there, live checks on it use pattern extraction and the registry and advisory paths only; the two bundled examples replay recorded runs. The action has not run on GitHub yet.

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
   - Which OSV records describe the claimed vulnerability ("matching"): a record whose own id is the claimed id, and only such records, when there is one. For a claimed CVE, every record that lists it, except a GitHub advisory whose `database_specific.nvd_published_at` (when NVD published the CVE GitHub attached to it) is more than 7 days from the claimed CVE's own publication date. OSV merges aliases transitively, so without this rule lodash's 2021 advisory would count as the advisory for CVE-2026-4800, a 2026 CVE about an incomplete fix. Records without that date evidence (PYSEC and others) are kept.
   - If the matching records disagree about the claimed version, the verdict is `unverifiable`, and the reason names each record and what it says (real example: Werkzeug 1.0.1 and CVE-2023-46136, where GitHub's record starts at 2.0.0rc1 and PYSEC-2023-221 at 0). Records left out are listed in the notes.
   - Licences: deps.dev's SPDX expression first, then `license_expression`, `license` and classifiers on PyPI, or `license` on npm. "BSD" claimed against "BSD-3-Clause" is supported; "BSD-3-Clause" claimed against the vague classifier "BSD License" is unverifiable; a licence that is only one part of an `AND` expression is unverifiable.
   - Each verdict carries the URL it came from and, as its quote, the exact field and value it relied on, for example `affected[requests].ranges.events: [{"introduced": "2.3.0"}, {"fixed": "2.31.0"}]`.
3. **Documentation claims: Tavily, scoped to the official docs.** For `parameter_exists`, `api_behavior`, `other_external` and `deprecated` (when no registry field answers it):
   - The official documentation domain comes from, in order: the Python standard library (`docs.python.org`), Node.js built-ins (`nodejs.org`) and JavaScript built-ins (`developer.mozilla.org`); a small curated map of vendors and languages (Stripe, GitHub, MDN, Node.js, TypeScript, React, Django, Go, Rust, PostgreSQL, Docker, Kubernetes, OpenAI, Tavily); the package's registry metadata (PyPI `project_urls` Documentation or Homepage, npm `homepage`).
   - A package whose only link is a code host (GitHub, GitLab) gets its repository page read directly, because restricting a search to `github.com` would let anyone's repository in.
   - Tavily Search runs with `include_domains` set to that domain. Tavily Extract then reads the top three results as whole pages in Markdown, so the headings survive. Translated pages are skipped when English ones exist. Before the three Extract slots are filled, results are ordered current documentation first (`docs.python.org/3/` before `/3.4/` or `/2.7/`, `nodejs.org/api/` before `latest-v18.x`), or pages for the claimed version first when the claim names one, and one URL is kept per page (anchors, trailing slashes, `?lang=` and `api-version` variants, `/latest/` and `/master/`, a locale prefix). If only version-specific pages come back, the report says so.
   - Each page is cut into sections by its headings: Markdown headings, and Sphinx definitions such as `classmethod datetime.utcnow()` (Python and Read the Docs pages), which count as the lowest heading level. Every window of text keeps its heading path (for example `File system > fs.rm(path[, options], callback)`) and its nearest API heading.
   - Windows are scored by the claim's terms (identifiers weigh most); windows about the claim's symbol (see anchoring below) rank first. At most six passages and 4,500 characters go to the jury, each shown with its heading path.
   - No official domain found means no search and an `unverifiable` verdict. Hearsay does not fall back to the open web.
4. **The jury (documentation claims only).** Several judge models independently read the claim and the passages and return `supported`, `contradicted` or `unverifiable`, a verbatim quote and the URL. A quote that does not appear in the passages (after normalising Unicode, quotes, dashes, Markdown and whitespace), is shorter than 15 characters or skips text with an ellipsis turns that judge's verdict into `unverifiable`. The URL reported is the passage where the quote really is. Then the **anchoring rule**: a supported or contradicted vote counts only if the passage holding its quote is about the claim's symbol (see below); otherwise it becomes `unverifiable`, with the reason recorded. If the judges agree, that is the verdict. If they disagree, an adjudicator model (a larger one) sees the claim, the passages and every judge's verdict, reasoning, quote and whether that quote was found and anchored, and decides under the same two rules. A judge whose output stays invalid after one repair round counts as `unverifiable`.
5. **Report.** JSON for machines and Markdown for a pull request comment: totals at the top, then per claim the verdict, the source URL, the quote, the decision path, each judge's verdict (with quote found, anchored, and why a vote was discarded) for jury claims, notes, and optionally the evidence passages with their heading paths.

### Anchoring

The quote rule proves that a quote exists in the documentation. Anchoring checks that the passage holding it is about the symbol the claim names (`fs.rm`, `requests.get`, `datetime.utcnow`), so a line from the `fs.rmdir` section cannot decide a claim about `fs.rm`. It applies to claims with a symbol; claims without one (for example the GitHub Actions limit) are not anchored. The rule (`src/hearsay/anchoring.py`):

1. If the passage sits under an API heading (a heading that is a call signature such as `fs.rmdir(path[, options], callback)`, or a Sphinx definition), the nearest such heading decides alone: it must name the symbol. Other functions mentioned in that section are cross-references and do not count. The `fs.rmdir` version history says "use `fs.rm` instead", and that does not make it about `fs.rm`.
2. Otherwise the passage's heading path or its text must name the symbol.

"Names the symbol" means one of these forms appears as a whole name, not followed by more identifier characters (so `fs.rmdir` and `fs.rmSync` do not name `fs.rm`):

| Form | Example for the symbol |
|---|---|
| dotted name, or a dotted suffix of two or more parts | `fs.rm(`; `datetime.datetime.utcnow` names `datetime.utcnow` |
| owner alias | `fsPromises.rm`, `fs.promises.rm` name `fs.rm` |
| Tavily's code rendering, a space after the last dot and a call | `requests. get('https://...')` names `requests.get` |
| possessive | `datetime.datetime's utcnow()` names `datetime.utcnow` |
| Sphinx cross-reference target | `[utcnow()](...#datetime.datetime.utcnow)` names `datetime.utcnow` |
| bare name, for a one-part symbol (a module) | `distutils` |

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
uv run hearsay web --env-file .env                         # web demo on http://127.0.0.1:8000
uv run hearsay mcp --env-file .env                         # MCP server on stdio
```

Options (for `check` and `claim`):

| Option | Effect |
|---|---|
| `--json` / `--markdown` | print the JSON or the Markdown report (Markdown is the default) |
| `--json-out PATH`, `--md-out PATH` | also write the report to a file |
| `--evidence` | include the passages the jury read in the Markdown report |
| `--no-llm` | no model calls: a pattern extractor finds install commands, pins, "X fixes CVE-..." sentences, "licensed under" phrases and npm deprecations (with negation read from the words right before "fix", "affected", "licensed" or "deprecated": "does not fix", "is no longer affected"), and only registry and advisory checks run |
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

## Web demo

`src/hearsay/web/` is a FastAPI app: server-rendered HTML, one stylesheet and a small script (a character counter and a busy state while a check runs). There is no frontend build step, and the page loads nothing from other sites.

```sh
uv run hearsay web --env-file .env      # http://127.0.0.1:8000
```

**The page.** Paste a pull request description or an agent's answer, or open a bundled example. The report shows the totals, then each claim with its verdict, the decision path (registry, advisory, jury, adjudicator), the source URL and the quote. For documentation claims the quote is highlighted inside the passage it was found in, and every vote is listed: what the model answered, what counted after the rules, whether its quote was found in the evidence, whether it came from a section about the claim's symbol, and why a vote was discarded. The passages the jury read are under "Evidence". Screenshots are in `docs/screenshots/`.

**The API.**

| Endpoint | Returns |
|---|---|
| `POST /api/check` with `{"text": "..."}` | the report JSON, the same as `hearsay check --json` |
| `POST /api/check` with `{"example": "agent-pr"}` | a bundled example's report |
| `GET /api/examples`, `GET /api/examples/{id}` | the bundled examples, one example's report |
| `GET /healthz` | status, whether models and Tavily are configured, Tavily calls used today |

```sh
curl -s localhost:8000/api/check -H 'content-type: application/json' \
  -d '{"text": "Upgrading urllib3 to 1.26.5 fixes CVE-2023-43804."}'
```

Report responses carry `X-Hearsay-Run` (`example` or `live`) and one `X-Hearsay-Notice` header per notice (for example "model calls are not configured"). Errors are JSON, `{"error": "...", "message": "..."}`, with status 400, 413, 429 or 503, and `Retry-After` where it applies.

**Bundled examples.** `src/hearsay/web/demo/bundle.json.gz` holds the two example inputs (`examples/agent-pr.md`, `examples/chat-answer.md`), the model settings they were recorded with, and the cached answers their runs read: registry, OSV and deps.dev responses (minus fields Hearsay never reads), model replies, and Tavily answers cut down to the documentation passages the runs used (see "Third-party text in the repository" below). Opening an example runs the normal pipeline against that snapshot with the network refused, a Tavily budget of zero and a model client that cannot connect. So it makes no API calls and shows the same report when every limit below is reached. A test replays both examples and compares them with `examples/*.report.json`. Live checks read the snapshot after their own cache, so an edited example reuses the answers the bundle holds; a reused Tavily answer holds only the passages the bundled runs used. The page says which models recorded an example; the current bundle was recorded with the local development stand-in. To rebuild it after the examples are re-run (for example with Nemotron once the Token Factory key exists):

```sh
uv run hearsay check examples/agent-pr.md      # fills .hearsay-cache with the current settings
uv run hearsay check examples/chat-answer.md
uv run python -m hearsay.web.demo build --env-file .env
```

The build stops if any answer is missing from the cache.

**Limits for a public demo.** All are environment variables.

| Variable | Default | Meaning |
|---|---|---|
| `HEARSAY_WEB_MAX_CHARS` | 8000 | longest text accepted (413 and a message above it) |
| `HEARSAY_TAVILY_MAX_CALLS` | 20 | new Tavily calls per check (the existing per-run cap) |
| `HEARSAY_WEB_TAVILY_DAILY_CAP` | 40 | new Tavily calls per UTC day for the whole demo; cached answers are free and not limited |
| `HEARSAY_WEB_RATE_LIMIT`, `HEARSAY_WEB_RATE_WINDOW` | 6, 600 | live checks per client address per window in seconds (429 with `Retry-After`) |
| `HEARSAY_WEB_MAX_CONCURRENT` | 2 | live checks running at once (503 when busy) |
| `HEARSAY_WEB_TRUST_FORWARDED` | off | take the client address from the left-most `X-Forwarded-For` entry; set it behind a proxy |
| `HEARSAY_WEB_REPO_URL` | none | link to the source repository in the footer |

- Bundled examples, and text identical to one, do not count against any limit.
- When a Tavily limit stops a lookup, that claim is `unverifiable` with the reason, and the page says which limit was reached.
- Request bodies larger than the text limit allows are refused before they are read (413; 411 without `Content-Length`).
- Keys come only from environment variables; the page never asks for one. `hearsay web` does not read a `.env` in the working directory, only `--env-file`.
- Without model settings, live checks use the pattern extractor and the page says so. Without a Tavily key, documentation claims are unverifiable and the page says so.
- Responses carry a Content-Security-Policy that allows only the app's own script and stylesheet; input is escaped and only `http(s)` URLs become links.

## MCP server

`hearsay mcp` runs an MCP server on stdio, built on the official MCP Python SDK (`mcp` 2.x, `MCPServer`). It lets a coding agent check a statement before making it.

| Tool | Argument | For |
|---|---|---|
| `hearsay_claim` | `sentence` | one statement, for example "requests 2.31.0 fixes CVE-2023-32681" |
| `hearsay_check` | `text` | a draft pull request description or answer |

Both return structured content with a published output schema, `{totals, claims: [{id, statement, type, verdict, path, source_url, quote, reason, source_sentence}], models_used, notes}`, and a short text summary with one line per claim:

```text
1 claim: 0 supported, 1 contradicted, 0 unverifiable.
- CONTRADICTED (advisory): urllib3 1.26.5 fixes CVE-2023-43804. urllib3 1.26.5 is still affected by CVE-2023-43804 (GHSA-v845-jxx5-vc9f). The fix is in 1.26.17. Source: https://api.osv.dev/v1/vulns/GHSA-v845-jxx5-vc9f Quote: "affected[urllib3].ranges.events: [{"introduced": "0"}, {"fixed": "1.26.17"}]"
```

The tools are marked read-only. The server also sends instructions to the client: check a fact with `hearsay_claim` before stating it, do not make a contradicted statement, say so when a claim is unverifiable. Settings come from the environment or `--env-file`; a `.env` in the agent's working directory is not read. Each tool call has its own Tavily budget (`HEARSAY_TAVILY_MAX_CALLS`). Without model settings the tools use the pattern extractor and say so in `notes`.

Claude Code:

```sh
claude mcp add hearsay -- uv --directory /path/to/hearsay run hearsay mcp --env-file /path/to/hearsay/.env
```

Codex:

```sh
codex mcp add hearsay -- uv --directory /path/to/hearsay run hearsay mcp --env-file /path/to/hearsay/.env
```

or in `~/.codex/config.toml`:

```toml
[mcp_servers.hearsay]
command = "uv"
args = ["--directory", "/path/to/hearsay", "run", "hearsay", "mcp", "--env-file", "/path/to/hearsay/.env"]
```

Keys can be passed with `-e KEY=value` (Claude Code) or `--env KEY=value` (Codex) instead of a file. `uv --directory` runs the server inside the Hearsay checkout, so every project shares its `.hearsay-cache`. To make an agent use the tools without being asked, add a line to its instructions (`CLAUDE.md`, `AGENTS.md`), for example: "Before stating a package version, CVE fix, licence, documented parameter or deprecation, check it with hearsay_claim."

## GitHub Action

`action.yml` is a composite action that runs Hearsay on a pull request and keeps one comment with the Markdown report up to date. `examples/github-workflow.yml` is a workflow to copy.

- It checks the pull request title and description from the event payload. With `include-bot-comments: "true"` it also checks comments by bot accounts and by the logins in `agent-logins`, and an `issue_comment` event from such an account runs the check again. Hearsay's own comment, found by a hidden marker, is never checked.
- It updates its earlier comment, or creates one. With no claims and no earlier comment it posts nothing, unless `comment-on-empty: "true"`.
- With `fail-on-contradicted: "true"` the step fails (exit status 2) when any claim is contradicted.
- It writes the full report to the job summary and sets the outputs `claims`, `supported`, `contradicted`, `unverifiable` and `comment-url`.
- With `cache: "true"` (the default) Hearsay's cache is kept between runs with `actions/cache`, so a re-run after an edit reuses earlier answers.
- Inputs reach the script only through environment variables, and the third-party actions it uses (`astral-sh/setup-uv`, `actions/cache`) are pinned to commits.
- It never checks out or runs the pull request's code, which is why the example uses `pull_request_target`: pull requests from forks then get the secrets and a write token too.

| Input | Default | Meaning |
|---|---|---|
| `github-token` | `github.token` | reads and writes the comment (`pull-requests: write`) |
| `tavily-api-key` | none | Tavily key; without it documentation claims are unverifiable |
| `llm-api-key` | none | key for the model endpoint |
| `llm-base-url` | Token Factory | OpenAI-compatible endpoint |
| `extract-model`, `judge-models`, `adjudicator-model` | none | model ids; without them only install commands, pins and CVE sentences are checked |
| `fail-on-contradicted` | `false` | fail the check on any contradicted claim |
| `include-bot-comments` | `false` | also check bot and agent comments |
| `agent-logins` | none | comma-separated logins to treat as agents |
| `comment-on-empty` | `false` | comment even when no claims are found |
| `tavily-max-calls` | 20 | new Tavily calls per run |
| `cache` | `true` | keep the cache between runs |

The action has not run on GitHub yet. The script it runs, `python -m hearsay.github_action`, was run locally against saved events (`tests/fixtures/action/`), the way the composite step calls it, with `--dry-run` so that it prints the comment instead of calling the GitHub API:

```sh
GITHUB_EVENT_PATH=tests/fixtures/action/pull_request.json GITHUB_REPOSITORY=example-org/payments-service \
  uv run python -m hearsay.github_action --dry-run --comment-out comment.md
```

`examples/github-action-comment.md` is the comment from that run (development stand-in models, Tavily answers from the cache).

## Deployment (Render)

- `Dockerfile`: two stages on `python:3.12-slim`. uv installs the locked dependencies without the dev tools; the app runs as an unprivileged user (uid 10001) under uvicorn on `$PORT` (Render sets it; 8000 otherwise). The cache is `/tmp/hearsay-cache`; the bundled examples do not need it.
- `render.yaml`: a Blueprint for one free web service with the Docker runtime and the health check `/healthz`. Keys and model ids are declared with `sync: false`, so Render asks for them when the Blueprint is created and nothing secret is in the file. In the Render dashboard: New, Blueprint, pick the repository, fill in the values.
- Free instances stop after 15 minutes without traffic and start again on the next request, which is slow. Their filesystem is not kept, so the cache starts empty after each start.

```sh
docker build -t hearsay .
docker run --rm -p 8000:8000 --env-file .env hearsay    # http://localhost:8000
```

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

The web demo's limits have their own variables (see "Web demo"). Values written as `<placeholder>` count as unset. Model calls use temperature 0 and JSON mode. Reasoning blocks (`<think>...</think>`) and code fences around the JSON are tolerated; the JSON itself is validated strictly.

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
- Whether a quote actually entails the verdict. The quote rule proves that the text exists in the source and anchoring that its passage is about the claimed symbol; neither proves that the text says what the verdict says.
- Private packages, private registries and private pull requests.

## Examples

`examples/` holds the inputs and the reports of real runs against live PyPI, npm, OSV, deps.dev, GitHub and Tavily, with the **local development stand-in** (qwen2.5:7b extractor, qwen2.5:3b and qwen2.5:7b judges, qwen2.5:7b adjudicator), not with Nemotron. The reports were last re-rendered from the cache, so their "Calls this run" lines show cache hits.

| Input | Report |
|---|---|
| `agent-pr.md`: an agent-style PR description with true, false, unverifiable and own-code claims | `agent-pr.report.md`, `.json` |
| `chat-answer.md`: an agent-style chat answer | `chat-answer.report.md`, `.json` |
| `gesiscss/gesis_surf_backend#67` (a public Dependabot PR), with `--no-llm` | `github-pr-dependabot.report.md`, `.json` |
| `tests/fixtures/action/pull_request.json`, a saved `pull_request` event with the `agent-pr.md` text, through the GitHub Action's script | `github-action-comment.md` |

What the stand-in got right and wrong (a handful of claims, not an accuracy measurement):

- **Registry and advisory claims (9 across the two inputs, plus 2 version claims in the Dependabot PR): all as expected.** Including: urllib3 1.26.5 does not fix CVE-2023-43804 (fixed in 1.26.17); `fastapi==0.200.0` does not exist; `pydantic-settings-extra` is on neither registry; requests is Apache-2.0, not MIT; lodash 4.17.21 is not affected by CVE-2021-23337 by that CVE's advisory, with a note that the 2026 advisory OSV merges with it was written for another CVE and is not used.
- **Documentation claims (7), with section-aware passages and anchoring: 5 as expected, 2 unverifiable, none wrong.**
  - As expected: `datetime.utcnow()` deprecated in 3.12 (supported, quote from the `classmethod datetime.utcnow()` definition), "distutils was removed in Python 3.10" (contradicted: "Deprecated since version 3.10, removed in version 3.12."), the GitHub Actions 256-job matrix limit (supported; no symbol, so not anchored), `Array.prototype.at()` with negative indexes (supported), and `fs.rm` supports `recursive` (supported: both judges quoted "`recursive` If true, perform a recursive removal." from the `fs.rm(path[, options], callback)` section).
  - Unverifiable, false claim: "`requests.get` accepts a `max_retries` parameter". One judge answered contradicted without a quote; the passages only describe `max_retries` on `HTTPAdapter`.
  - Unverifiable, true claim: "Stripe refunds accept an idempotency key". The 7B judge's quote was 14 characters long. Anchoring would have discarded any quote anyway, because the extractor gave the symbol `Stripe.refunds` and no Stripe page names it. That is the conservative outcome, but it means anchoring is only as good as the symbol the extractor writes.
- **The `fs.rm` case before and after.** Before, Tavily Extract returned query-ranked chunks without headings. The judges and the adjudicator called the claim contradicted, quoting "v25.0.0 | Remove `recursive` option." from the version history of `fs.rmdir`, a different function. Now the evidence is mostly the `fs.rm` and `fsPromises.rm` sections. A quote from the `fs.rmdir` section is discarded by the anchoring rule, even though that section's history table says "use `fs.rm` instead"; `tests/test_docs.py` replays exactly that case on the recorded page.
- **Extraction:** the 7B extractor missed two claims in `agent-pr.md` (the documented `timeout` parameter and the GitHub Actions limit), and skipped the own-code claim and the opinion as intended. Before the validation rules above were added, it also set `negated` wrongly in both directions, cited a wrong sentence number, and typed the GitHub Actions sentence as `affected_by_vulnerability`.
- **Jury behaviour:** the 3B and 7B judges often quoted text that is not in the passages, quoted the claim itself, or gave quotes too short to check; the quote rule turned those votes into `unverifiable`, which is why several documentation claims went to the adjudicator. Verdicts on the same claims also changed between prompt revisions, so these runs say little about prompt quality for Nemotron.

## Development

```sh
uv run pytest                              # 224 tests, no network, no model calls
uv run python tests/record_fixtures.py     # re-record fixtures (see below)
```

The suite replays real responses recorded in `tests/fixtures/cache` through a read-only cache, refuses any socket connection, and uses a scripted fake model. `tests/record_fixtures.py` records PyPI, npm, deps.dev, OSV and GitHub answers (trimmed to the fields Hearsay reads) and copies Tavily answers from the development cache with network access to Tavily blocked, so recording spends no Tavily credits. Tavily answers are trimmed as described next.

### Third-party text in the repository

Fixtures and the web demo bundle replay real runs from cached answers, and a cached Tavily Extract answer is a whole documentation page. Those pages belong to their publishers (Stripe's documentation, for one, is not openly licensed; Python, Node.js, MDN and GitHub docs are, but the same rule applies to all), so what is committed keeps only what a run used (`src/hearsay/trim.py`):

- the windows shown to the judges, each re-emitted under its original heading lines so it parses back to the same text, heading path and API heading; the fixtures also keep the few windows tests pick by name (`tests/support.py`, `KEEP_WINDOWS`);
- a one-line heading for a page none of whose windows was used;
- search results' URLs, titles and scores, and a snippet only where it replaced a failed extract;
- registry, OSV, deps.dev and GitHub JSON, minus fields Hearsay never reads.

Selection scores each window on its own text and heading path, so a page cut down to its chosen windows yields the same choice, the same judge prompts and the same cached replies. `tests/record_fixtures.py` and `python -m hearsay.web.demo build` trim automatically and replay the runs from the trimmed data; they refuse to write if any verdict, source, quote or passage changes. `tests/test_committed_text.py` fails if a committed fixture, the bundle, an example report or a benchmark result holds more than 20,000 characters of page text for one page (the judges see at most 4,500 characters per claim). The development cache (`.hearsay-cache/`, never committed) keeps the full pages, so a rebuild with other models trims again from complete data.

Layout: `src/hearsay/` has `extract.py` (model extraction), `patterns.py` (no-model extraction), `registries.py`, `versions.py`, `licenses.py` and `deterministic.py` (registry and advisory checks), `docs_domain.py`, `tavily.py`, `passages.py` (page sections and windows), `anchoring.py`, `jury.py`, `quotes.py` and `docs.py` (documentation path), `pipeline.py` (routing), `report.py`, `cli.py`, `cache.py`, `http.py` and `llm.py`. Delivery: `web/` (`app.py`, `limits.py`, `views.py`, `demo.py` and the bundle, templates and static files), `mcp_server.py` and `github_action.py` (the script behind `action.yml`). The web, MCP and action tests (`tests/test_web.py`, `test_mcp_server.py`, `test_github_action.py`) use the bundle, the recorded fixtures, a scripted model, the MCP SDK's in-process client and a fake GitHub API.

## Known problems

- **Anchoring depends on the extractor's symbol.** A made-up symbol (`Stripe.refunds`) makes every quote unanchored. A claim without a symbol is not anchored at all.
- **Anchoring is weak on prose guides.** On a user guide whose sections are full of code samples (the requests "Advanced Usage" page), nearly every section names `requests.get`, so anchoring does not separate them.
- **Some headings that mention a call are not API sections.** Node's "DEP0147: fs.rmdir(path, { recursive: true })" counts as a heading for `fs.rmdir`. Its advice to use `fs.rm(path, { recursive: true, force: true })` therefore cannot support an `fs.rm` claim.
- **Whole pages are large.** Extracting whole pages keeps the headings but can be big (Node's `all.html` is 2.5 MB of Markdown). It costs no extra Tavily credits, and the cache stores it once.
- **Extraction recall** depends on the extractor model; the safety net only covers install commands and pins.
- **OSV alias merging** is undone only for GitHub advisories, which carry the publication date of their own CVE. A merged PYSEC or other record that is really about another CVE still counts as matching; if it disagrees, the verdict is unverifiable rather than wrong.
- **No ecosystem stated** and a package name that exists on both PyPI and npm makes version and licence claims `unverifiable`.
- **Old documentation versions.** Tavily can return pages of old releases. For "`json.dumps` accepts a `sort_keys` parameter" it returned the Python 2.7, 3.4 and 3.5 source text pages. (In that run both stand-in judges also quoted an example with its double quotes changed to single quotes, so both quotes were discarded and the claim was unverifiable.)
- **The demo's limits live in memory.** The daily Tavily cap and the rate limit start again when the process restarts, and a free Render instance restarts after 15 idle minutes. The Tavily key's own monthly limit is the hard stop.
- **Client address on Render.** Render does not document how it sets `X-Forwarded-For`. With `HEARSAY_WEB_TRUST_FORWARDED` the left-most entry is used; a client can forge it to get around the per-address limit, not the daily cap. Check the header on the deployed service.
- **The bundle must be rebuilt** when prompts, the pipeline or the model settings change, because replays then miss answers (the test that replays the examples fails).

## License

MIT, see `LICENSE`.
