"""The web demo: paste an agent's text or open a bundled example and read the report.

    uv run hearsay web                        # http://127.0.0.1:8000
    uvicorn hearsay.web.app:app --port 8000   # what the Docker image runs

Pages: GET /, GET /examples/{id}, POST /check (form).
API: POST /api/check, GET /api/examples, GET /api/examples/{id}, GET /healthz.

Keys come only from environment variables (see README, "Web demo").
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pydantic import BaseModel, ConfigDict
from starlette.concurrency import run_in_threadpool

from .._version import __version__
from ..cache import Cache
from ..config import Settings
from ..http import Http
from ..llm import ChatModel, OpenAICompatibleClient
from ..models import Report, Usage
from ..pipeline import Context, check
from .demo import BUNDLE_PATH, Bundle, Example, LayeredCache, empty_bundle, load_bundle, normalize_input
from .limits import BodySizeLimit, DailyCap, DemoTavily, Gate, RateLimiter
from .views import PATH_HELP, PATH_LABEL, VERDICT_LABEL, code_spans, report_view, safe_url

log = logging.getLogger("hearsay.web")

HERE = Path(__file__).parent


def _int(env: dict[str, str], name: str, default: int) -> int:
    try:
        return int(env.get(name, default))
    except ValueError:
        return default


@dataclass
class WebConfig:
    max_chars: int = 8000
    rate_limit: int = 6  # live checks per address ...
    rate_window: int = 600  # ... per this many seconds
    tavily_daily_cap: int = 40  # new Tavily calls per UTC day, whole demo
    max_concurrent: int = 2  # live checks running at once
    trust_forwarded: bool = False  # take the client address from X-Forwarded-For (behind a proxy)
    repo_url: str | None = None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "WebConfig":
        env = dict(os.environ if env is None else env)
        return cls(
            max_chars=_int(env, "HEARSAY_WEB_MAX_CHARS", 8000),
            rate_limit=_int(env, "HEARSAY_WEB_RATE_LIMIT", 6),
            rate_window=_int(env, "HEARSAY_WEB_RATE_WINDOW", 600),
            tavily_daily_cap=_int(env, "HEARSAY_WEB_TAVILY_DAILY_CAP", 40),
            max_concurrent=_int(env, "HEARSAY_WEB_MAX_CONCURRENT", 2),
            trust_forwarded=env.get("HEARSAY_WEB_TRUST_FORWARDED", "").lower() in ("1", "true", "yes"),
            repo_url=env.get("HEARSAY_WEB_REPO_URL") or None,
        )

    @property
    def max_body_bytes(self) -> int:
        # A form-encoded character can take up to 12 bytes (%XX for each UTF-8 byte).
        return self.max_chars * 12 + 16_384


@dataclass
class Outcome:
    report: Report | None = None
    run: str = "live"  # "example" or "live"
    example: Example | None = None
    notices: list[str] = field(default_factory=list)
    error: str | None = None
    error_code: str | None = None
    status: int = 200
    retry_after: int | None = None


class Demo:
    """Runs checks for the web app, with the demo's limits applied."""

    def __init__(
        self,
        config: WebConfig,
        bundle: Bundle,
        *,
        settings_factory: Callable[[], Settings] = Settings.from_env,
        transport: httpx.BaseTransport | None = None,
        llm: ChatModel | None = None,
    ):
        self.config = config
        self.bundle = bundle
        self.settings_factory = settings_factory
        self.transport = transport
        self.llm_override = llm
        self.rate = RateLimiter(config.rate_limit, config.rate_window)
        self.daily = DailyCap(config.tavily_daily_cap)
        self.gate = Gate(config.max_concurrent)

    # -------------------------------------------------------------- contexts

    def _context(self, settings: Settings, use_llm: bool) -> Context:
        usage = Usage()
        cache = LayeredCache(Cache(settings.cache_dir), self.bundle.cache)
        http = Http(cache, usage, transport=self.transport, timeout=settings.http_timeout)
        tavily = None
        if settings.tavily_api_key:
            ledger = settings.cache_dir / "tavily-ledger.jsonl" if settings.cache_dir else None
            tavily = DemoTavily(
                http, settings.tavily_api_key, max_calls=settings.tavily_max_calls, ledger=ledger, daily=self.daily
            )
        llm: ChatModel | None = None
        if use_llm:
            llm = self.llm_override or OpenAICompatibleClient(
                settings.llm_base_url,
                settings.llm_api_key,
                cache,
                usage,
                timeout=settings.llm_timeout,
                max_tokens=settings.llm_max_tokens,
                transport=self.transport,
            )
        return Context(settings, usage, cache, http, tavily, llm)

    def models_configured(self, settings: Settings | None = None) -> bool:
        settings = settings or self.settings_factory()
        return self.llm_override is not None or not settings.llm_problems()

    # -------------------------------------------------------------- runs

    def example(self, example_id: str) -> Outcome:
        example = self.bundle.get(example_id)
        if example is None:
            return Outcome(error="There is no bundled example with that name.", error_code="unknown_example", status=404)
        try:
            report = self.bundle.report(example_id)
        except RuntimeError:
            log.exception("example replay failed")
            return Outcome(
                example=example,
                error="This example could not be replayed from the bundle. The server log has the details.",
                error_code="example_unavailable",
                status=500,
            )
        return Outcome(report=report, run="example", example=example)

    def check_text(self, text: str, client: str) -> Outcome:
        example = self.bundle.match(text)
        if example is not None:
            return self.example(example.id)
        text = normalize_input(text)
        if not text:
            return Outcome(error="Paste some text to check.", error_code="empty", status=400)
        if len(text) > self.config.max_chars:
            return Outcome(
                error=(
                    f"The text is {len(text):,} characters long; this demo checks at most {self.config.max_chars:,}. "
                    "Shorten it, or run Hearsay locally, where there is no limit."
                ),
                error_code="too_long",
                status=413,
            )
        wait = self.rate.hit(client)
        if wait is not None:
            minutes = max(1, round(wait / 60))
            return Outcome(
                error=(
                    f"This address has used its {self.config.rate_limit} live checks for "
                    f"{self.config.rate_window // 60} minutes. Try again in about {minutes} minute"
                    f"{'s' if minutes != 1 else ''}. The bundled examples do not count against this limit."
                ),
                error_code="rate_limited",
                status=429,
                retry_after=int(wait) + 1,
            )
        if not self.gate.try_enter():
            return Outcome(
                error=(
                    f"{self.config.max_concurrent} checks are already running on this small server. "
                    "Try again in a minute; the bundled examples open right away."
                ),
                error_code="busy",
                status=503,
                retry_after=30,
            )
        try:
            return self._live(text)
        finally:
            self.gate.leave()

    def _live(self, text: str) -> Outcome:
        settings = self.settings_factory()
        use_llm = self.models_configured(settings)
        ctx = self._context(settings, use_llm)
        try:
            report = check(text, context=ctx)
        except Exception:
            log.exception("live check failed")
            return Outcome(
                error="The check failed with an internal error. The server log has the details.",
                error_code="internal_error",
                status=500,
            )
        finally:
            ctx.close()
        notices = []
        if not use_llm:
            notices.append(
                "Model calls are not configured on this server, so claims were found by patterns only "
                "(install commands, version pins, \"fixes CVE-...\" sentences, licence phrases, npm deprecations) "
                "and documentation claims were not checked."
            )
        elif ctx.tavily is None:
            notices.append("Tavily is not configured on this server, so documentation claims are unverifiable.")
        capped = getattr(ctx.tavily, "capped", None)
        if capped == "request":
            notices.append(
                f"This check reached the limit of {settings.tavily_max_calls} new Tavily calls per check; "
                "the documentation claims after that point are unverifiable."
            )
        elif capped == "daily":
            notices.append(
                f"The demo's daily limit of {self.config.tavily_daily_cap} new Tavily calls is used up. "
                "Documentation claims whose answers are not cached are unverifiable until 00:00 UTC. "
                "The bundled examples still work."
            )
        for err in report.extraction.errors:
            notices.append(f"Claim extraction reported a problem: {err}")
        return Outcome(report=report, run="live", notices=notices)


# ------------------------------------------------------------------ app


class CheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str | None = None
    example: str | None = None


SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "base-uri 'none'; form-action 'self'; frame-ancestors 'none'; object-src 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "X-Frame-Options": "DENY",
}


def client_address(request: Request, trust_forwarded: bool) -> str:
    """The caller's address. Behind a proxy, the left-most X-Forwarded-For entry."""
    if trust_forwarded:
        forwarded = request.headers.get("x-forwarded-for", "")
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def _templates() -> Environment:
    env = Environment(
        loader=FileSystemLoader(HERE / "templates"),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["safe_url"] = safe_url
    env.filters["code_spans"] = code_spans
    env.filters["thousands"] = lambda n: f"{n:,}"
    env.globals.update(VERDICT_LABEL=VERDICT_LABEL, PATH_LABEL=PATH_LABEL, PATH_HELP=PATH_HELP)
    return env


def create_app(
    config: WebConfig | None = None,
    *,
    bundle: Bundle | None = None,
    settings_factory: Callable[[], Settings] = Settings.from_env,
    transport: httpx.BaseTransport | None = None,
    llm: ChatModel | None = None,
) -> FastAPI:
    config = config or WebConfig.from_env()
    if bundle is None:
        bundle = load_bundle(BUNDLE_PATH) if BUNDLE_PATH.is_file() else empty_bundle()
    demo = Demo(config, bundle, settings_factory=settings_factory, transport=transport, llm=llm)
    templates = _templates()

    app = FastAPI(title="Hearsay", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.demo = demo
    app.add_middleware(BodySizeLimit, max_bytes=config.max_body_bytes)
    app.mount("/static", StaticFiles(directory=HERE / "static"), name="static")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.method == "POST":
            response.headers["Cache-Control"] = "no-store"
        return response

    def page(request: Request, outcome: Outcome | None = None, text: str = "", status: int = 200) -> HTMLResponse:
        settings = settings_factory()
        html = templates.get_template("index.html").render(
            config=config,
            settings=settings,
            examples=bundle.examples,
            text=text,
            outcome=outcome,
            claims=report_view(outcome.report) if outcome and outcome.report else [],
            version=__version__,
            models_configured=demo.models_configured(settings),
            tavily_configured=bool(settings.tavily_api_key),
            tavily_left_today=demo.daily.remaining,
        )
        response = HTMLResponse(html, status_code=status)
        if outcome and outcome.retry_after:
            response.headers["Retry-After"] = str(outcome.retry_after)
        return response

    @app.get("/", response_class=HTMLResponse)
    def index(request: Request) -> HTMLResponse:
        return page(request)

    @app.get("/examples/{example_id}", response_class=HTMLResponse)
    def example_page(request: Request, example_id: str) -> HTMLResponse:
        outcome = demo.example(example_id)
        text = outcome.example.text if outcome.example else ""
        return page(request, outcome, text, outcome.status)

    @app.post("/check", response_class=HTMLResponse)
    async def check_form(request: Request) -> HTMLResponse:
        form = await request.form()
        text = form.get("text")
        text = text if isinstance(text, str) else ""
        address = client_address(request, config.trust_forwarded)
        outcome = await run_in_threadpool(demo.check_text, text, address)
        return page(request, outcome, text, outcome.status)

    @app.get("/check")
    def check_get() -> RedirectResponse:
        return RedirectResponse("/", status_code=303)

    def api_error(outcome: Outcome) -> JSONResponse:
        headers = {"Retry-After": str(outcome.retry_after)} if outcome.retry_after else None
        return JSONResponse(
            {"error": outcome.error_code, "message": outcome.error}, status_code=outcome.status, headers=headers
        )

    def api_report(outcome: Outcome) -> Response:
        if outcome.report is None:
            return api_error(outcome)
        headers = [("X-Hearsay-Run", outcome.run)]
        if outcome.example is not None:
            headers.append(("X-Hearsay-Example", outcome.example.id))
        headers += [("X-Hearsay-Notice", n.encode("ascii", "replace").decode()) for n in outcome.notices]
        response = Response(outcome.report.model_dump_json(indent=2), media_type="application/json")
        for name, value in headers:
            response.headers.append(name, value)
        return response

    @app.post("/api/check")
    def api_check(request: Request, body: CheckRequest) -> Response:
        if body.example is not None and body.text is None:
            return api_report(demo.example(body.example))
        if body.text is None or body.example is not None:
            return JSONResponse(
                {"error": "bad_request", "message": 'Send {"text": "..."} or {"example": "<id>"}.'}, status_code=400
            )
        return api_report(demo.check_text(body.text, client_address(request, config.trust_forwarded)))

    @app.get("/api/examples")
    def api_examples() -> list[dict]:
        return [{"id": e.id, "title": e.title, "kind": e.kind, "summary": e.summary} for e in bundle.examples]

    @app.get("/api/examples/{example_id}")
    def api_example(example_id: str) -> Response:
        return api_report(demo.example(example_id))

    @app.get("/healthz")
    def healthz() -> dict:
        settings = settings_factory()
        return {
            "status": "ok",
            "version": __version__,
            "examples": len(bundle.examples),
            "models_configured": demo.models_configured(settings),
            "tavily_configured": bool(settings.tavily_api_key),
            "tavily_calls_today": demo.daily.used,
            "tavily_daily_cap": config.tavily_daily_cap,
        }

    return app


def __getattr__(name: str):
    # `uvicorn hearsay.web.app:app` builds the app on first access, from the environment.
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
