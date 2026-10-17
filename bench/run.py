"""Run Hearsay on the benchmark claims and score it against hand-checked labels.

    uv run python bench/run.py --dry-run                       # validate the dataset, no model calls
    uv run python bench/run.py --no-llm --part registry        # registry/advisory part, no model
    uv run python bench/run.py --config jury                   # Hearsay as configured
    uv run python bench/run.py --config single                 # one judge, no adjudicator
    uv run python bench/run.py --config no-anchor              # anchoring disabled (ablation)

Model ids come from the environment (HEARSAY_EXTRACT_MODEL, HEARSAY_JUDGE_MODELS,
HEARSAY_ADJUDICATOR_MODEL, HEARSAY_BENCH_SINGLE_MODEL), loaded from .env and --env-file
like the hearsay CLI. Every HTTP, Tavily and model call goes through Hearsay's own
on-disk cache, so a rerun of the same configuration costs nothing.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

BENCH = Path(__file__).resolve().parent
ROOT = BENCH.parent
sys.path.insert(0, str(ROOT / "src"))

import hearsay  # noqa: E402
from hearsay import docs as hearsay_docs  # noqa: E402
from hearsay.cache import Cache  # noqa: E402
from hearsay.config import TOKEN_FACTORY_BASE_URL, Settings, load_env_file  # noqa: E402
from hearsay.http import Http, HttpError  # noqa: E402
from hearsay.llm import OpenAICompatibleClient  # noqa: E402
from hearsay.models import CLAIM_FIELDS, Claim, ClaimResult, ClaimType, Usage, Verdict  # noqa: E402
from hearsay.pipeline import ConfigError, Context  # noqa: E402
from hearsay.quotes import normalize  # noqa: E402

DATASET = BENCH / "claims.jsonl"
LABELS = ("supported", "contradicted", "unverifiable")
ROUTES = ("registry", "advisory", "docs")
PARTS = {"registry": ("registry", "advisory"), "docs": ("docs",)}
CONFIGS = ("jury", "single", "no-anchor")
EXTRACTIONS = ("model", "patterns", "gold")
FIELDS = ("id", "sentence", "type", "label", "route", "source_url", "source_quote", "notes", "claim")
JSON_HOSTS = {"pypi.org", "registry.npmjs.org", "api.osv.dev", "api.deps.dev", "api.github.com", "cveawg.mitre.org"}
PAGE_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; hearsay-bench; +https://github.com)"}


# ---------------------------------------------------------------- dataset


def load_dataset(path: Path = DATASET) -> list[dict]:
    rows = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{path}:{n}: invalid JSON: {exc}") from None
    return rows


def gold_claim(row: dict) -> Claim:
    fields = {k: v for k, v in (row.get("claim") or {}).items() if k in CLAIM_FIELDS}
    return Claim(
        id=row["id"],
        type=ClaimType(row["type"]),
        statement=row["sentence"],
        source_sentence=row["sentence"],
        negated=bool((row.get("claim") or {}).get("negated", False)),
        origin="gold",
        **fields,
    )


def schema_problems(rows: list[dict]) -> list[str]:
    problems = []
    seen = set()
    for i, row in enumerate(rows, 1):
        rid = row.get("id", f"line {i}")
        missing = [f for f in FIELDS if f not in row]
        extra = sorted(set(row) - set(FIELDS))
        if missing:
            problems.append(f"{rid}: missing fields {missing}")
        if extra:
            problems.append(f"{rid}: unknown fields {extra}")
        if rid in seen:
            problems.append(f"{rid}: duplicate id")
        seen.add(rid)
        if row.get("label") not in LABELS:
            problems.append(f"{rid}: label {row.get('label')!r} is not one of {LABELS}")
        if row.get("route") not in ROUTES:
            problems.append(f"{rid}: route {row.get('route')!r} is not one of {ROUTES}")
        try:
            ClaimType(row.get("type"))
        except ValueError:
            problems.append(f"{rid}: type {row.get('type')!r} is not a Hearsay claim type")
            continue
        sentence = row.get("sentence") or ""
        if not sentence.strip() or "\n" in sentence:
            problems.append(f"{rid}: sentence must be one non-empty line")
        for name in ("sentence", "notes"):
            if "\u2014" in (row.get(name) or ""):
                problems.append(f"{rid}: {name} contains a long dash")
        url = row.get("source_url")
        if url is not None and not re.match(r"https?://", url):
            problems.append(f"{rid}: source_url is not an http(s) URL")
        if row.get("label") != "unverifiable":
            if not url:
                problems.append(f"{rid}: a supported/contradicted label needs a source_url")
            if not (row.get("source_quote") or "").strip():
                problems.append(f"{rid}: a supported/contradicted label needs a source_quote")
        if not isinstance(row.get("claim"), dict):
            problems.append(f"{rid}: claim must be an object")
            continue
        unknown = set(row["claim"]) - set(CLAIM_FIELDS) - {"negated"}
        if unknown:
            problems.append(f"{rid}: claim has unknown keys {sorted(unknown)}")
        try:
            missing_claim = gold_claim(row).missing_fields()
        except Exception as exc:  # pydantic validation
            problems.append(f"{rid}: claim is not a valid Hearsay claim: {exc}")
            continue
        if missing_claim:
            problems.append(f"{rid}: claim needs {missing_claim}")
    return problems


# ---------------------------------------------------------------- source checks (dry run)


class _Text(HTMLParser):
    BLOCK = {"p", "div", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "pre", "dt", "dd", "br", "section",
             "table", "ul", "ol", "blockquote", "td", "th", "article", "header", "footer", "nav"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip += 1
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.skip = max(0, self.skip - 1)
        if tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def page_text(raw: str) -> str:
    if "<html" not in raw[:5000].lower() and "<!doctype" not in raw[:500].lower():
        return raw
    parser = _Text()
    parser.feed(raw)
    return html.unescape("".join(parser.out))


_SEGMENT = re.compile(r"([^.\[\]]+)((?:\[[^\]]+\])*)")


def _resolve(node: object, path: str) -> list:
    """Every value at a dotted path. Lists fan out; [name] picks the elements whose
    package.name (or name) is `name`, [0] picks by index."""
    nodes = [node]
    for seg in path.split("."):
        m = _SEGMENT.fullmatch(seg)
        if not m:
            return []
        key, selectors = m.group(1), re.findall(r"\[([^\]]+)\]", m.group(2))
        nxt = []
        for n in nodes:
            for item in (n if isinstance(n, list) else [n]):
                if isinstance(item, dict) and key in item:
                    nxt.append(item[key])
        for sel in selectors:
            picked = []
            for value in nxt:
                if not isinstance(value, list):
                    continue
                if sel.isdigit():
                    picked += value[int(sel) : int(sel) + 1]
                else:
                    for el in value:
                        name = (el.get("package") or {}).get("name") if isinstance(el, dict) else None
                        name = name or (el.get("name") if isinstance(el, dict) else None)
                        if isinstance(name, str) and name.lower() == sel.lower():
                            picked.append(el)
            nxt = picked
        nodes = nxt
    return nodes


def field_quote_problems(data: object, quote: str) -> list[str]:
    """A field quote is `path: <JSON value>` assertions joined by "; ". Each path must
    resolve in the response to a value equal to the given one."""
    problems = []
    for part in re.split(r";\s+(?=[\w.\[\]-]+: )", quote):
        path, sep, raw = part.partition(": ")
        if not sep:
            problems.append(f"cannot read {part!r} as path: value")
            continue
        try:
            want = json.loads(raw)
        except json.JSONDecodeError:
            problems.append(f"value of {path} is not JSON: {raw!r}")
            continue
        found = _resolve(data, path)
        flat = []
        for f in found:  # ranges[].events: compare with each range's events
            flat.extend(f if isinstance(f, list) and f and isinstance(f[0], list) else [f])
        if want not in flat and not any(isinstance(f, list) and want in f for f in found):
            problems.append(f"{path} is {json.dumps(found, ensure_ascii=False)[:200]}, not {raw}")
    return problems


def check_source(http: Http, url: str, quote: str, offline: bool) -> dict:
    """Fetch (cache first) and check that the quote is in the source.

    Pages: the quote must appear verbatim (after Hearsay's normalisation of
    whitespace, quote marks and dashes). JSON APIs: the quote is a set of
    `path: value` assertions that must hold in the response; a quote
    `HTTP 404: <body>` expects a 404 with that JSON body.
    """
    host = (urlparse(url).hostname or "").lower()
    is_json = host in JSON_HOSTS
    namespace, headers = ("http", None) if is_json else ("bench-sources", PAGE_HEADERS)
    key = {"method": "GET", "url": url, "params": None, "json": None, "headers": headers}
    cached = not Cache.is_missing(http.cache.get(namespace, key))
    out = {"url": url, "from_cache": cached, "status": None, "quote_found": None, "problem": None}
    if offline and not cached:
        out["problem"] = "not in the cache (--offline)"
        return out
    try:
        res = http.get(url, headers=headers, namespace=namespace)
    except HttpError as exc:
        out["problem"] = str(exc)
        return out
    out["status"] = res.status
    expect = 404 if quote.startswith("HTTP 404") else 200
    if res.status != expect:
        out["problem"] = f"expected HTTP {expect}, got {res.status}"
        return out
    if not quote:
        return out
    if is_json and expect == 404:
        body = quote.partition(": ")[2]
        try:
            ok = json.loads(body) == res.data
        except json.JSONDecodeError:
            ok = False
        out["quote_found"] = ok
        if not ok:
            out["problem"] = f"404 body is {json.dumps(res.data)[:200]}, not {body}"
    elif is_json:
        bad = field_quote_problems(res.data, quote)
        out["quote_found"] = not bad
        if bad:
            out["problem"] = "; ".join(bad)
    else:
        text = page_text(res.data if isinstance(res.data, str) else json.dumps(res.data))
        found = normalize(quote) in normalize(text)
        out["quote_found"] = found
        if not found:
            out["problem"] = "quote not found in the page text"
    return out


def dry_run(rows: list[dict], settings: Settings, offline: bool, live: bool = False) -> int:
    problems = schema_problems(rows)
    usage = Usage()
    http = Http(Cache(settings.cache_dir, refresh=live), usage, timeout=settings.http_timeout)
    checked: dict[tuple[str, str], dict] = {}
    for row in rows:
        url, quote = row.get("source_url"), row.get("source_quote") or ""
        if not url:
            continue
        key = (url, quote)
        if key not in checked:
            checked[key] = check_source(http, url, quote, offline)
        res = checked[key]
        mark = "ok" if not res["problem"] else "PROBLEM"
        where = "cache" if res["from_cache"] else "live"
        found = {True: "quote found", False: "quote NOT found", None: "no quote to check"}[res["quote_found"]]
        print(f"{row['id']:4} {mark:7} HTTP {res['status']} ({where}) {found}: {url}", file=sys.stderr)
        if res["problem"]:
            problems.append(f"{row['id']}: {url}: {res['problem']}")
    counts = Counter((r.get("route"), r.get("label")) for r in rows)
    types = Counter(r.get("type") for r in rows)
    print(f"\n{len(rows)} claims; {len(checked)} distinct source checks; "
          f"HTTP requests {usage.http_requests}, cache hits {usage.http_cache_hits}; no model or Tavily calls.")
    print("by route and label: " + ", ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(counts.items())))
    print("by type: " + ", ".join(f"{k}={v}" for k, v in sorted(types.items())))
    if problems:
        print(f"\n{len(problems)} problems:")
        for p in problems:
            print(f"  - {p}")
        return 1
    print("dataset OK")
    return 0


# ---------------------------------------------------------------- token metering


class TokenMeter(Cache):
    """The same cache, counting the token usage stored with each model answer.

    `fresh` counts calls made in this run; `cached` counts answers replayed
    from the cache (their usage as recorded when they were first made).
    """

    def __init__(self, inner: Cache):
        super().__init__(inner.root, refresh=inner.refresh)
        self.fresh: Counter = Counter()
        self.cached: Counter = Counter()

    @staticmethod
    def _add(counter: Counter, usage: object) -> None:
        if isinstance(usage, dict):
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                if isinstance(usage.get(k), int):
                    counter[k] += usage[k]
            counter["calls_with_usage"] += 1

    def get(self, namespace, request):
        value = super().get(namespace, request)
        if namespace == "llm" and not Cache.is_missing(value) and isinstance(value, dict):
            self._add(self.cached, value.get("usage"))
        return value

    def put(self, namespace, request, response):
        super().put(namespace, request, response)
        if namespace == "llm" and isinstance(response, dict):
            self._add(self.fresh, response.get("usage"))


class _NoAnchor:
    """Stand-in for hearsay.anchoring.Anchor that never anchors (ablation)."""

    @staticmethod
    def for_claim(claim):
        return None


# ---------------------------------------------------------------- running


def build_context(args, settings: Settings) -> tuple[Context, TokenMeter | None, dict]:
    config = {"config": "no-llm" if args.no_llm else args.config, "extraction": args.extraction}
    if not args.no_llm:
        if args.config == "single":
            single = args.single_model or os.environ.get("HEARSAY_BENCH_SINGLE_MODEL") or (
                settings.judge_models[0] if settings.judge_models else None
            )
            if not single:
                raise ConfigError("single: set HEARSAY_BENCH_SINGLE_MODEL or HEARSAY_JUDGE_MODELS")
            settings.judge_models = [single]
            settings.adjudicator_model = single  # never called: one judge always agrees with itself
            config["single_model"] = single
        if args.config == "no-anchor":
            hearsay_docs.Anchor = _NoAnchor  # check_docs_claim looks Anchor up in this module
    ctx = Context.create(settings, use_llm=not args.no_llm)
    meter = None
    if isinstance(ctx.llm, OpenAICompatibleClient):
        meter = TokenMeter(ctx.llm.cache)
        ctx.llm.cache = meter
    if ctx.llm is not None:
        base = settings.llm_base_url
        config.update(
            llm_base_url=base,
            extract_model=settings.extract_model if args.extraction == "model" else None,
            judge_models=list(settings.judge_models),
            adjudicator_model=None if args.config == "single" else settings.adjudicator_model,
            nemotron_on_token_factory=base.rstrip("/") == TOKEN_FACTORY_BASE_URL.rstrip("/"),
        )
    return ctx, meter, config


def pick_result(results: list[ClaimResult], gold_type: str) -> tuple[ClaimResult | None, str]:
    """The sentence's verdict: the first extracted claim of the labelled type, else the only claim."""
    same = [r for r in results if r.claim.type.value == gold_type]
    if same:
        return same[0], "type matches" + (f" ({len(same)} of that type)" if len(same) > 1 else "")
    if len(results) == 1:
        return results[0], f"only claim, typed {results[0].claim.type.value}"
    if results:
        return results[0], f"no claim of type {gold_type}; first of {len(results)}"
    return None, "no claim extracted"


def outcome(label: str, predicted: str) -> str:
    if label == "unverifiable":
        return "correct" if predicted == "unverifiable" else "overclaimed"
    if predicted == label:
        return "correct"
    if predicted == "unverifiable":
        return "abstained"
    return "wrong"


def _usage_delta(before: dict, after: dict) -> dict:
    return {k: after[k] - before[k] for k in after}


def run_one(ctx: Context, meter: TokenMeter | None, row: dict, extraction: str) -> dict:
    u0 = ctx.usage.model_dump()
    t0 = (Counter(meter.fresh), Counter(meter.cached)) if meter else None
    tavily0 = ctx.tavily.calls_made if ctx.tavily else 0
    started = time.time()
    if extraction == "gold":
        report = hearsay.check_claims([gold_claim(row)], context=ctx)
    else:
        report = hearsay.check(row["sentence"], context=ctx)
    chosen, how = pick_result(report.results, row["type"])
    predicted = chosen.verdict.value if chosen else "unverifiable"
    rec = {
        "id": row["id"],
        "type": row["type"],
        "route": row["route"],
        "label": row["label"],
        "predicted": predicted,
        "outcome": outcome(row["label"], predicted),
        "path": chosen.path.value if chosen else "none",
        "selection": how,
        "sentence": row["sentence"],
        "source_url": chosen.source_url if chosen else None,
        "quote": chosen.quote if chosen else None,
        "reason": chosen.reason if chosen else "",
        "notes": chosen.notes if chosen else [],
        "claim": chosen.claim.model_dump(exclude_defaults=True) if chosen else None,
        "all_claims": [
            {"type": r.claim.type.value, "statement": r.claim.statement, "verdict": r.verdict.value, "path": r.path.value}
            for r in report.results
        ],
        "judges": [v.model_dump(exclude={"reasoning"}) for v in (chosen.judges if chosen else [])],
        "adjudicator": chosen.adjudicator.model_dump(exclude={"reasoning"}) if chosen and chosen.adjudicator else None,
        "extraction_errors": report.extraction.errors,
        "seconds": round(time.time() - started, 2),
    }
    reason = rec["reason"].lower()
    if "budget" in reason or "lookup failed" in reason or "tavily" in reason and "returned http" in reason:
        rec["infra_problem"] = rec["reason"]  # not Hearsay's judgement: budget or service failure
    usage = _usage_delta(u0, ctx.usage.model_dump())
    usage["tavily_calls"] = (ctx.tavily.calls_made if ctx.tavily else 0) - tavily0
    if meter and t0:
        usage["tokens_fresh"] = dict(meter.fresh - t0[0])
        usage["tokens_cached"] = dict(meter.cached - t0[1])
    rec["usage"] = usage
    return rec


# ---------------------------------------------------------------- summary


def _rate(n: int, d: int) -> float | None:
    return round(n / d, 3) if d else None


def _block(recs: list[dict]) -> dict:
    c = Counter(r["outcome"] for r in recs)
    decisive = [r for r in recs if r["predicted"] != "unverifiable"]
    return {
        "n": len(recs),
        "correct": c["correct"],
        "accuracy": _rate(c["correct"], len(recs)),
        "abstained": c["abstained"],
        "wrong": c["wrong"],
        "overclaimed": c["overclaimed"],
        "decisive": len(decisive),
        "decisive_precision": _rate(sum(r["outcome"] == "correct" for r in decisive), len(decisive)),
    }


def summarize(recs: list[dict], config: dict, meta: dict) -> dict:
    by = lambda key: {k: _block([r for r in recs if r[key] == k]) for k in sorted({r[key] for r in recs})}  # noqa: E731
    confusion: dict[str, Counter] = defaultdict(Counter)
    for r in recs:
        confusion[r["label"]][r["predicted"]] += 1
    cost: Counter = Counter()
    fresh: Counter = Counter()
    cached: Counter = Counter()
    for r in recs:
        u = r["usage"]
        for k in ("http_requests", "http_cache_hits", "tavily_calls", "tavily_cache_hits", "llm_calls", "llm_cache_hits"):
            cost[k] += u.get(k, 0)
        fresh.update(u.get("tokens_fresh") or {})
        cached.update(u.get("tokens_cached") or {})
    infra = [r["id"] for r in recs if r.get("infra_problem")]
    return {
        **meta,
        "configuration": config,
        "overall": _block(recs),
        "by_label": by("label"),
        "by_type": by("type"),
        "by_route": by("route"),
        "by_path": by("path"),
        "confusion": {k: dict(v) for k, v in sorted(confusion.items())},
        "cost": {
            **dict(cost),
            "tokens_this_run": dict(fresh),
            "tokens_replayed_from_cache": dict(cached),
            "note": "tavily_calls and llm_calls are uncached calls made in this run; tokens are what the API reported "
            "(none for servers that do not report usage); replayed tokens are what the cached answers cost when made.",
        },
        "infra_problems": infra,
        "not_correct": [
            {"id": r["id"], "label": r["label"], "predicted": r["predicted"], "outcome": r["outcome"], "path": r["path"],
             "reason": r["reason"][:300]}
            for r in recs if r["outcome"] != "correct"
        ],
    }


def to_markdown(s: dict) -> str:
    cfg = s["configuration"]
    lines = [f"# Hearsay benchmark: {cfg['config']}, extraction {cfg['extraction']}", ""]
    lines.append(f"Run {s['run_at']} on {s['n_claims']} claims (dataset sha256 {s['dataset_sha256'][:12]}), "
                 f"hearsay {s['hearsay_version']}.")
    if cfg.get("llm_base_url"):
        lines.append(f"Models: base URL `{cfg['llm_base_url']}`, extractor `{cfg.get('extract_model')}`, judges "
                     f"`{', '.join(cfg.get('judge_models') or [])}`, adjudicator `{cfg.get('adjudicator_model')}`.")
        if not cfg.get("nemotron_on_token_factory"):
            lines.append("")
            lines.append("**Not Nemotron on Token Factory: these model-stage numbers come from another endpoint "
                         "(for example the local development stand-in) and are not a result.**")
    else:
        lines.append("No model calls (registry and advisory checks only).")
    o = s["overall"]
    lines += ["", "| | n | correct | accuracy | abstained | wrong | overclaimed | decisive precision |",
              "|---|---|---|---|---|---|---|---|"]

    def row(name, b):
        return (f"| {name} | {b['n']} | {b['correct']} | {b['accuracy']} | {b['abstained']} | {b['wrong']} | "
                f"{b['overclaimed']} | {b['decisive_precision']} |")

    lines.append(row("**all**", o))
    for group in ("by_label", "by_route", "by_type", "by_path"):
        for k, b in s[group].items():
            lines.append(row(f"{group[3:]}: {k}", b))
    lines += ["", "Abstained: truth supported/contradicted, Hearsay unverifiable. Wrong: supported for contradicted "
              "or the reverse (the costly error). Overclaimed: a decisive verdict on a claim labelled unverifiable. "
              "Decisive precision: share of supported/contradicted verdicts that were right.", "",
              "Confusion (rows: label, columns: Hearsay):", "",
              "| label | supported | contradicted | unverifiable |", "|---|---|---|---|"]
    for label, cols in s["confusion"].items():
        lines.append(f"| {label} | {cols.get('supported', 0)} | {cols.get('contradicted', 0)} | {cols.get('unverifiable', 0)} |")
    c = s["cost"]
    lines += ["", f"Cost this run: {c.get('tavily_calls', 0)} Tavily calls ({c.get('tavily_cache_hits', 0)} cached), "
              f"{c.get('llm_calls', 0)} model calls ({c.get('llm_cache_hits', 0)} cached), "
              f"{c.get('http_requests', 0)} HTTP requests ({c.get('http_cache_hits', 0)} cached). "
              f"Tokens this run: {c['tokens_this_run'] or 'none reported'}; "
              f"replayed from cache: {c['tokens_replayed_from_cache'] or 'none reported'}."]
    if s["infra_problems"]:
        lines += ["", f"**Budget or service problems (not Hearsay's judgement): {', '.join(s['infra_problems'])}.**"]
    if s["not_correct"]:
        lines += ["", "Not correct:", ""]
        for r in s["not_correct"]:
            lines.append(f"- `{r['id']}` label {r['label']}, Hearsay {r['predicted']} ({r['outcome']}, path {r['path']}): "
                         f"{r['reason']}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main


def select(rows: list[dict], args) -> list[dict]:
    if args.ids:
        wanted = [i.strip() for i in args.ids.split(",") if i.strip()]
        unknown = set(wanted) - {r["id"] for r in rows}
        if unknown:
            raise SystemExit(f"unknown ids: {sorted(unknown)}")
        rows = [r for r in rows if r["id"] in wanted]
    if args.part:
        rows = [r for r in rows if r["route"] in PARTS[args.part]]
    if args.limit:
        rows = rows[: args.limit]
    return rows


def load_settings(args) -> Settings:
    if (ROOT / ".env").is_file():
        load_env_file(ROOT / ".env")
    for path in args.env_file:
        load_env_file(path)
    settings = Settings.from_env()
    if settings.cache_dir is not None and not settings.cache_dir.is_absolute():
        settings.cache_dir = ROOT / settings.cache_dir  # Hearsay's cache, wherever the bench is started from
    if args.tavily_max_calls is not None:
        settings.tavily_max_calls = args.tavily_max_calls
    return settings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Score Hearsay against bench/claims.jsonl.")
    p.add_argument("--dry-run", action="store_true", help="validate the dataset and its sources; no model or Tavily calls")
    p.add_argument("--offline", action="store_true", help="with --dry-run: use only cached sources")
    p.add_argument("--live", action="store_true", help="with --dry-run: fetch every source again (the cache is rewritten)")
    p.add_argument("--config", choices=CONFIGS, default="jury", help="jury (default), single or no-anchor")
    p.add_argument("--extraction", choices=EXTRACTIONS, help="model (default), patterns (with --no-llm) or gold claims")
    p.add_argument("--no-llm", action="store_true", help="Hearsay's --no-llm path: no model calls, registry/advisory only")
    p.add_argument("--single-model", help="model for --config single (default HEARSAY_BENCH_SINGLE_MODEL, else the first judge)")
    p.add_argument("--part", choices=sorted(PARTS), help="registry (registry and advisory routes) or docs")
    p.add_argument("--ids", help="comma-separated claim ids")
    p.add_argument("--limit", type=int, help="first N selected claims")
    p.add_argument("--env-file", action="append", default=[], metavar="PATH", help="load settings (repeatable)")
    p.add_argument("--tavily-max-calls", type=int, help="override HEARSAY_TAVILY_MAX_CALLS for this run")
    p.add_argument("--out", help="output directory (default bench/results/<config>-<extraction>[-<part>])")
    p.add_argument("--dataset", default=str(DATASET), help="claims file")
    args = p.parse_args(argv)

    rows = load_dataset(Path(args.dataset))
    settings = load_settings(args)
    if args.dry_run:
        if args.offline and args.live:
            p.error("--offline and --live exclude each other")
        return dry_run(select(rows, args), settings, args.offline, args.live)

    if args.extraction is None:
        args.extraction = "patterns" if args.no_llm else "model"
    if args.extraction == "patterns" and not args.no_llm:
        p.error("--extraction patterns is the --no-llm path; add --no-llm")
    if args.extraction == "model" and args.no_llm:
        p.error("--no-llm has no model extractor; use --extraction patterns or gold")
    problems = schema_problems(rows)
    if problems:
        print("dataset problems (run --dry-run):\n  " + "\n  ".join(problems), file=sys.stderr)
        return 1
    selected = select(rows, args)
    try:
        ctx, meter, config = build_context(args, settings)
    except ConfigError as exc:
        print(f"bench: {exc}", file=sys.stderr)
        return 1

    name = args.out or str(BENCH / "results" / "-".join(
        x for x in (config["config"], args.extraction, args.part or ("ids" if args.ids else None)) if x))
    out = Path(name)
    out.mkdir(parents=True, exist_ok=True)
    recs = []
    with (out / "results.jsonl").open("w", encoding="utf-8") as fh:
        for i, row in enumerate(selected, 1):
            rec = run_one(ctx, meter, row, args.extraction)
            recs.append(rec)
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            u = rec["usage"]
            print(f"[{i}/{len(selected)}] {rec['id']:4} label {rec['label']:12} hearsay {rec['predicted']:12} "
                  f"{rec['outcome']:11} path {rec['path']:11} tavily {u['tavily_calls']} llm {u['llm_calls']}",
                  file=sys.stderr)
    meta = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "hearsay_version": hearsay.__version__,
        "dataset": str(Path(args.dataset).resolve().relative_to(ROOT)) if Path(args.dataset).resolve().is_relative_to(ROOT) else args.dataset,
        "dataset_sha256": hashlib.sha256(Path(args.dataset).read_bytes()).hexdigest(),
        "n_claims": len(recs),
        "selection": {"part": args.part, "ids": args.ids, "limit": args.limit},
    }
    summary = summarize(recs, config, meta)
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md = to_markdown(summary)
    (out / "summary.md").write_text(md, encoding="utf-8")
    print(md)
    print(f"wrote {out}/results.jsonl, summary.json, summary.md", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
