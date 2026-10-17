"""OpenAI-compatible chat client (Nebius Token Factory in production), cached on disk.

Also the JSON helpers every model stage uses: lenient unwrapping of the
reply (reasoning tags, code fences), strict validation by the caller, and
one repair round on invalid output.
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Protocol, TypeVar

import httpx

from .cache import Cache
from .models import Usage

T = TypeVar("T")


class LLMError(RuntimeError):
    pass


class ChatModel(Protocol):
    def complete(self, model: str, messages: list[dict[str, str]], *, json_mode: bool = True) -> str: ...


class OpenAICompatibleClient:
    """POST {base_url}/chat/completions. Works with Token Factory, vLLM, Ollama and others."""

    def __init__(
        self,
        base_url: str,
        api_key: str | None,
        cache: Cache,
        usage: Usage,
        *,
        timeout: float = 300.0,
        max_tokens: int = 2048,
        transport: httpx.BaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.cache = cache
        self.usage = usage
        self.max_tokens = max_tokens
        self.client = httpx.Client(timeout=timeout, transport=transport)

    def complete(self, model: str, messages: list[dict[str, str]], *, json_mode: bool = True) -> str:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": self.max_tokens,
        }
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        key = {"base_url": self.base_url, **body}
        cached = self.cache.get("llm", key)
        if not Cache.is_missing(cached):
            self.usage.llm_cache_hits += 1
            return cached["content"]

        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            resp = self.client.post(f"{self.base_url}/chat/completions", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise LLMError(f"model call failed: {exc.__class__.__name__}: {exc}") from None
        self.usage.llm_calls += 1
        if resp.status_code != 200:
            raise LLMError(f"model call returned HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        try:
            content = data["choices"][0]["message"].get("content") or ""
        except (KeyError, IndexError, TypeError):
            raise LLMError(f"unexpected response shape: {str(data)[:300]}") from None
        self.cache.put("llm", key, {"content": content, "usage": data.get("usage")})
        return content


_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.S)


def parse_json_object(text: str) -> dict:
    """Unwrap a model reply into a JSON object. Raises ValueError otherwise.

    Accepts reasoning blocks and Markdown code fences around the object; the
    object itself must be valid JSON.
    """
    s = _THINK.sub("", text or "").strip()
    m = _FENCE.match(s)
    if m:
        s = m.group(1).strip()
    try:
        value = json.loads(s)
    except json.JSONDecodeError:
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("reply is not JSON") from None
        try:
            value = json.loads(s[start : end + 1])
        except json.JSONDecodeError as exc:
            raise ValueError(f"reply is not valid JSON: {exc.msg}") from None
    if not isinstance(value, dict):
        raise ValueError("reply is JSON but not an object")
    return value


def ask_json(
    llm: ChatModel,
    model: str,
    messages: list[dict[str, str]],
    validate: Callable[[dict], T],
) -> tuple[T | None, list[str]]:
    """Ask for JSON, validate it, retry once with the errors. Returns (value, errors)."""
    errors: list[str] = []
    reply = llm.complete(model, messages)
    try:
        return validate(parse_json_object(reply)), errors
    except (ValueError, TypeError) as exc:
        errors.append(f"attempt 1: {_short(exc)}")
    repair = messages + [
        {"role": "assistant", "content": reply},
        {
            "role": "user",
            "content": f"Your reply was invalid: {_short(errors[-1])}. "
            "Reply again with only the corrected JSON object, following the format exactly.",
        },
    ]
    reply2 = llm.complete(model, repair)
    try:
        return validate(parse_json_object(reply2)), errors
    except (ValueError, TypeError) as exc:
        errors.append(f"attempt 2: {_short(exc)}")
    return None, errors


def _short(exc: object, limit: int = 400) -> str:
    text = str(exc).replace("\n", " ")
    return text if len(text) <= limit else text[: limit - 3] + "..."
