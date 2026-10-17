"""On-disk cache keyed by the request.

Every HTTP, Tavily and LLM call goes through here, so a rerun of the same
input costs nothing and gives the same report. Secrets are never part of
the stored request (callers pass them separately).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

_MISSING = object()


def request_key(namespace: str, request: Any) -> str:
    blob = json.dumps({"ns": namespace, "req": request}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Cache:
    """A directory of JSON files: <root>/<namespace>/<key[:2]>/<key>.json.

    root=None disables the cache. refresh=True skips reads but still writes,
    which re-fetches everything once and stores the new answers.
    """

    def __init__(self, root: str | Path | None, *, refresh: bool = False):
        self.root = Path(root) if root is not None else None
        self.refresh = refresh

    def _path(self, namespace: str, key: str) -> Path:
        assert self.root is not None
        return self.root / namespace / key[:2] / f"{key}.json"

    def get(self, namespace: str, request: Any) -> Any:
        """Return the cached response, or the module-level _MISSING sentinel."""
        if self.root is None or self.refresh:
            return _MISSING
        path = self._path(namespace, request_key(namespace, request))
        try:
            with path.open(encoding="utf-8") as fh:
                return json.load(fh)["response"]
        except FileNotFoundError:
            return _MISSING
        except (json.JSONDecodeError, KeyError):
            return _MISSING

    def put(self, namespace: str, request: Any, response: Any) -> None:
        if self.root is None:
            return
        path = self._path(namespace, request_key(namespace, request))
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"namespace": namespace, "request": request, "response": response}
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)
        os.replace(tmp, path)

    @staticmethod
    def is_missing(value: Any) -> bool:
        return value is _MISSING
