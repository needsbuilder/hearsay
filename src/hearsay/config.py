"""Configuration from environment variables (and optional .env files)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

TOKEN_FACTORY_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"


def load_env_file(path: str | Path, *, override: bool = False) -> list[str]:
    """Read KEY=VALUE lines into os.environ. Returns the names that were set.

    Existing environment variables win unless override is true. Values are
    never printed or logged.
    """
    names = []
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export ") :]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not key:
            continue
        if override or key not in os.environ:
            os.environ[key] = value
            names.append(key)
    return names


def _clean(value: str | None) -> str | None:
    """Treat empty values and unfilled <placeholders> as unset."""
    if value is None:
        return None
    value = value.strip()
    if not value or (value.startswith("<") and value.endswith(">")):
        return None
    return value


@dataclass
class Settings:
    llm_base_url: str = TOKEN_FACTORY_BASE_URL
    llm_api_key: str | None = None
    extract_model: str | None = None
    judge_models: list[str] = field(default_factory=list)
    adjudicator_model: str | None = None
    tavily_api_key: str | None = None
    tavily_max_calls: int = 20
    cache_dir: Path | None = Path(".hearsay-cache")
    refresh_cache: bool = False
    http_timeout: float = 30.0
    llm_timeout: float = 300.0
    llm_max_tokens: int = 2048

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "Settings":
        env = dict(os.environ if env is None else env)
        judges = [m.strip() for m in env.get("HEARSAY_JUDGE_MODELS", "").split(",")]
        judges = [m for m in (_clean(j) for j in judges) if m]
        cache_dir = env.get("HEARSAY_CACHE_DIR", ".hearsay-cache")
        return cls(
            llm_base_url=_clean(env.get("HEARSAY_LLM_BASE_URL")) or TOKEN_FACTORY_BASE_URL,
            llm_api_key=_clean(env.get("HEARSAY_LLM_API_KEY")),
            extract_model=_clean(env.get("HEARSAY_EXTRACT_MODEL")),
            judge_models=judges,
            adjudicator_model=_clean(env.get("HEARSAY_ADJUDICATOR_MODEL")),
            tavily_api_key=_clean(env.get("TAVILY_API_KEY")),
            tavily_max_calls=int(env.get("HEARSAY_TAVILY_MAX_CALLS", "20")),
            cache_dir=None if cache_dir.lower() in ("", "off", "none") else Path(cache_dir),
            llm_timeout=float(env.get("HEARSAY_LLM_TIMEOUT", "300")),
        )

    def llm_problems(self) -> list[str]:
        """What is missing for the model stages (extraction and jury)."""
        problems = []
        if not self.extract_model:
            problems.append("HEARSAY_EXTRACT_MODEL is not set")
        if not self.judge_models:
            problems.append("HEARSAY_JUDGE_MODELS is not set")
        if not self.adjudicator_model:
            problems.append("HEARSAY_ADJUDICATOR_MODEL is not set")
        if not self.llm_api_key:
            problems.append("HEARSAY_LLM_API_KEY is not set")
        return problems
