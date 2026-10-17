"""Bundled examples for the web demo, replayed from a snapshot of the cache.

`demo/bundle.json.gz` holds each example's input text, the model settings it
was recorded with, and every cached answer (registry, OSV, deps.dev, Tavily,
model) its run read. It is built from a local cache with

    uv run python -m hearsay.web.demo build --env-file dev/ollama.env

Replaying an example runs the normal pipeline against that snapshot only: the
network is refused, Tavily has a budget of zero and the model client cannot
connect, so a replay makes no API calls and works when every cap is reached.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from ..cache import _MISSING, Cache, request_key
from ..config import Settings, load_env_file
from ..http import Http
from ..llm import OpenAICompatibleClient
from ..models import ModelConfig, Report, Usage
from ..pipeline import Context, check
from ..tavily import TavilyClient

BUNDLE_PATH = Path(__file__).parent / "demo" / "bundle.json.gz"
BUNDLE_FORMAT = 1


@dataclass(frozen=True)
class ExampleSpec:
    id: str
    title: str
    kind: str  # what the text is: a pull request description or a chat answer
    file: str  # input file under examples/
    summary: str


EXAMPLES = [
    ExampleSpec(
        id="agent-pr",
        title="Agent pull request",
        kind="Pull request description",
        file="agent-pr.md",
        summary="Dependency bumps with CVE fixes, licences, a made-up package, documented parameters and deprecations.",
    ),
    ExampleSpec(
        id="chat-answer",
        title="Agent chat answer",
        kind="Chat answer",
        file="chat-answer.md",
        summary="GitHub Actions limits, an npm deprecation, JavaScript and Node.js API behaviour, a licence.",
    ),
]


# ------------------------------------------------------------------ caches


class SnapshotCache(Cache):
    """Read-only cache answered from {namespace: {key: response}}. Records misses."""

    def __init__(self, entries: dict[str, dict[str, Any]]):
        super().__init__(None)
        self.entries = entries
        self.misses: list[tuple[str, Any]] = []

    def get(self, namespace: str, request: Any) -> Any:
        try:
            return self.entries[namespace][request_key(namespace, request)]
        except KeyError:
            self.misses.append((namespace, request))
            return _MISSING

    def put(self, namespace: str, request: Any, response: Any) -> None:
        return None


class LayeredCache(Cache):
    """A writable cache in front of the read-only snapshot.

    Live requests on the demo read their own cache first, then the snapshot,
    and write only to their own cache. An edited example therefore reuses
    every registry and Tavily answer the bundle already holds.
    """

    def __init__(self, primary: Cache, fallback: SnapshotCache | None):
        super().__init__(primary.root, refresh=primary.refresh)
        self.primary = primary
        self.fallback = fallback

    def get(self, namespace: str, request: Any) -> Any:
        value = self.primary.get(namespace, request)
        if Cache.is_missing(value) and self.fallback is not None and not self.primary.refresh:
            value = self.fallback.get(namespace, request)
        return value

    def put(self, namespace: str, request: Any, response: Any) -> None:
        self.primary.put(namespace, request, response)


class RecordingCache(Cache):
    """Reads a cache directory, never writes, and remembers every answer it gave."""

    def __init__(self, root: Path):
        super().__init__(root)
        self.seen: dict[str, dict[str, Any]] = {}
        self.misses: list[tuple[str, Any]] = []

    def get(self, namespace: str, request: Any) -> Any:
        value = super().get(namespace, request)
        if Cache.is_missing(value):
            self.misses.append((namespace, request))
        else:
            self.seen.setdefault(namespace, {})[request_key(namespace, request)] = value
        return value

    def put(self, namespace: str, request: Any, response: Any) -> None:
        return None


def _no_network() -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"replay from the snapshot: no network ({request.url.host})", request=request)

    return httpx.MockTransport(handler)


def offline_context(models: ModelConfig | None, cache: Cache) -> Context:
    """A pipeline context that can only answer from `cache`.

    `models` are the settings the example was recorded with (they are part of
    the model cache keys); None replays a run without model calls.
    """
    settings = Settings(
        llm_base_url=(models.llm_base_url if models and models.llm_base_url else "http://replay.invalid/v1"),
        llm_api_key="replay",
        extract_model=models.extract_model if models else None,
        judge_models=list(models.judge_models) if models else [],
        adjudicator_model=models.adjudicator_model if models else None,
        tavily_api_key="replay",
        tavily_max_calls=0,
        cache_dir=None,
    )
    usage = Usage()
    http = Http(cache, usage, transport=_no_network(), retry_delay=0)
    tavily = TavilyClient(http, "replay", max_calls=0)
    llm = None
    if models is not None and models.extract_model:
        llm = OpenAICompatibleClient(settings.llm_base_url, "replay", cache, usage, transport=_no_network())
    return Context(settings, usage, cache, http, tavily, llm)


# ------------------------------------------------------------------ bundle


@dataclass
class Example:
    id: str
    title: str
    kind: str
    summary: str
    text: str
    models: ModelConfig | None
    recorded_with: str


@dataclass
class Bundle:
    examples: list[Example]
    cache: SnapshotCache
    built: str = ""
    _reports: dict[str, Report] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def get(self, example_id: str) -> Example | None:
        return next((e for e in self.examples if e.id == example_id), None)

    def match(self, text: str) -> Example | None:
        """The example whose text this is (line endings and outer whitespace ignored)."""
        wanted = normalize_input(text)
        return next((e for e in self.examples if normalize_input(e.text) == wanted), None)

    def report(self, example_id: str) -> Report:
        """Replay an example from the snapshot (once; later calls reuse the result)."""
        with self._lock:
            if example_id not in self._reports:
                example = self.get(example_id)
                if example is None:
                    raise KeyError(example_id)
                report, misses = replay(example, self.cache.entries)
                if misses:
                    raise RuntimeError(
                        f"example {example_id!r} is not fully in the bundle ({len(misses)} answers missing); "
                        "rebuild it with: python -m hearsay.web.demo build"
                    )
                self._reports[example_id] = report
            return self._reports[example_id].model_copy(deep=True)


def normalize_input(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def replay(example: Example, entries: dict[str, dict[str, Any]]) -> tuple[Report, list[tuple[str, Any]]]:
    cache = SnapshotCache(entries)
    ctx = offline_context(example.models, cache)
    try:
        report = check(example.text, context=ctx)
    finally:
        ctx.close()
    return report, cache.misses


def describe_models(models: ModelConfig | None) -> str:
    if models is None or not models.extract_model:
        return "Recorded without model calls (pattern extraction, registry and advisory checks only)."
    judges = ", ".join(models.judge_models)
    names = f"extractor {models.extract_model}; judges {judges}; adjudicator {models.adjudicator_model}"
    if "tokenfactory.nebius.com" in (models.llm_base_url or ""):
        return f"Recorded with Nebius Token Factory ({names})."
    return f"Recorded with the local development stand-in, not with Nemotron ({names})."


def load_bundle(path: Path = BUNDLE_PATH) -> Bundle:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    if data.get("format") != BUNDLE_FORMAT:
        raise ValueError(f"unsupported demo bundle format {data.get('format')!r} in {path}")
    examples = [
        Example(
            id=e["id"],
            title=e["title"],
            kind=e["kind"],
            summary=e["summary"],
            text=e["text"],
            models=ModelConfig.model_validate(e["models"]) if e.get("models") else None,
            recorded_with=e["recorded_with"],
        )
        for e in data["examples"]
    ]
    return Bundle(examples=examples, cache=SnapshotCache(data["cache"]), built=data.get("built", ""))


def empty_bundle() -> Bundle:
    return Bundle(examples=[], cache=SnapshotCache({}))


def build_bundle(
    examples_dir: Path,
    cache_dir: Path,
    models: ModelConfig,
    out: Path = BUNDLE_PATH,
    specs: list[ExampleSpec] = EXAMPLES,
) -> dict[str, Report]:
    """Replay every example from `cache_dir` without network and write the bundle.

    Fails if any answer is missing from the cache: run the example once with
    the CLI first (`hearsay check examples/<file>`), which fills the cache.
    """
    entries: dict[str, dict[str, Any]] = {}
    out_examples = []
    reports = {}
    for spec in specs:
        text = (examples_dir / spec.file).read_text(encoding="utf-8")
        recorder = RecordingCache(cache_dir)
        ctx = offline_context(models, recorder)
        try:
            report = check(text, context=ctx)
        finally:
            ctx.close()
        if recorder.misses:
            missing = ", ".join(sorted({ns for ns, _ in recorder.misses}))
            raise RuntimeError(
                f"{spec.file}: {len(recorder.misses)} answers are not in {cache_dir} ({missing}). "
                f"Run `hearsay check examples/{spec.file}` with the same settings first."
            )
        for ns, items in recorder.seen.items():
            entries.setdefault(ns, {}).update(items)
        reports[spec.id] = report
        out_examples.append(
            {
                "id": spec.id,
                "title": spec.title,
                "kind": spec.kind,
                "summary": spec.summary,
                "text": text,
                "models": models.model_dump(),
                "recorded_with": describe_models(models),
            }
        )
    payload = {
        "format": BUNDLE_FORMAT,
        "built": time.strftime("%Y-%m-%d"),
        "examples": out_examples,
        "cache": entries,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    with open(out, "wb") as fh:
        # mtime=0 keeps the file byte-identical when nothing changed.
        with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=9, mtime=0) as gz:
            gz.write(raw)
    return reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m hearsay.web.demo", description="Build the web demo's example bundle.")
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("build", help="replay the examples from a local cache and write the bundle")
    b.add_argument("--env-file", action="append", default=[], metavar="PATH", help="settings with the model ids the examples were run with")
    b.add_argument("--cache-dir", default=".hearsay-cache", help="cache to read (default .hearsay-cache)")
    b.add_argument("--examples-dir", default="examples", help="directory with the example inputs (default examples)")
    b.add_argument("--out", default=str(BUNDLE_PATH), help="bundle file to write")
    args = parser.parse_args(argv)

    for path in args.env_file:
        load_env_file(path, override=True)
    s = Settings.from_env()
    models = ModelConfig(
        llm_base_url=s.llm_base_url,
        extract_model=s.extract_model,
        judge_models=list(s.judge_models),
        adjudicator_model=s.adjudicator_model,
    )
    if not models.extract_model or not models.judge_models or not models.adjudicator_model:
        print("demo build: model ids are not set (use --env-file)", file=sys.stderr)
        return 1
    try:
        reports = build_bundle(Path(args.examples_dir), Path(args.cache_dir), models, Path(args.out))
    except RuntimeError as exc:
        print(f"demo build: {exc}", file=sys.stderr)
        return 1
    size = Path(args.out).stat().st_size
    for example_id, report in reports.items():
        t = report.totals
        print(f"{example_id}: {t.claims} claims, {t.supported} supported, {t.contradicted} contradicted, {t.unverifiable} unverifiable")
    print(f"wrote {args.out} ({size / 1024:.0f} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
