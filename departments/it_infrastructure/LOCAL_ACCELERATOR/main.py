"""LOCAL_ACCELERATOR: an on-disk result cache that makes repeated work instant.

Not hardware acceleration. compute(key, fn) returns the stored result for `key`
while it is fresh and otherwise calls fn(), stores what it returned and returns
that. Entries expire after their TTL, and when the cache holds more than
MAX_ENTRIES the least recently used are dropped. The cache survives restarts.

Values must be JSON. A failing fn() is reported and nothing is cached, so an
error is never served as a result.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

from velaris.agentkit.infra_store import State, fail, invalid, is_json, is_number, ok

NAME = "LOCAL_ACCELERATOR"
MAX_ENTRIES = 500
DEFAULT_TTL_S = 3600.0


class LOCAL_ACCELERATORAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = State(NAME, "cache.json")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    @staticmethod
    def _args_problem(key: Any, ttl_s: Any, now: Any) -> str:
        if not isinstance(key, str) or not key or len(key) > 512:
            return "key must be a non-empty string of at most 512 characters"
        if not is_number(ttl_s, 0.001):
            return "ttl_s must be a positive number"
        if now is not None and not is_number(now, 0):
            return "now must be a timestamp"
        return ""

    def get(self, key: str, now: Optional[float] = None) -> Dict[str, Any]:
        problem = self._args_problem(key, 1, now)
        if problem:
            return invalid(problem, hit=False)
        now = time.time() if now is None else now

        def read(data: Dict[str, Any]) -> Dict[str, Any]:
            stats = data.setdefault("stats", {"hits": 0, "misses": 0})
            entry = data.get("entries", {}).get(key)
            if entry is None or entry["expires"] <= now:
                data.get("entries", {}).pop(key, None)
                stats["misses"] += 1
                return {"status": "miss", "hit": False, "value": None}
            entry["used"] = now
            stats["hits"] += 1
            return ok(hit=True, value=entry["value"])
        return self._state.change(read)

    def put(self, key: str, value: Any, ttl_s: float = DEFAULT_TTL_S, now: Optional[float] = None) -> Dict[str, Any]:
        problem = self._args_problem(key, ttl_s, now)
        if problem or not is_json(value):
            return invalid(problem or "value must be JSON")
        now = time.time() if now is None else now

        def write(data: Dict[str, Any]) -> int:
            entries = data.setdefault("entries", {})
            entries[key] = {"value": value, "expires": now + ttl_s, "used": now}
            for old in sorted(entries, key=lambda k: entries[k]["used"])[:max(0, len(entries) - MAX_ENTRIES)]:
                del entries[old]
            return len(entries)
        return ok(entries=self._state.change(write))

    def compute(self, key: str, fn: Callable[[], Any], ttl_s: float = DEFAULT_TTL_S,
                now: Optional[float] = None) -> Dict[str, Any]:
        """The cached value for `key`, or fn()'s result (cached for ttl_s) if there is none."""
        if not callable(fn):
            return invalid("fn must be callable", hit=False)
        cached = self.get(key, now)
        if cached["status"] != "miss":
            return cached
        try:
            value = fn()
        except Exception as e:  # the callable is the caller's code: report, cache nothing
            return fail("compute_failed", f"{type(e).__name__}: {e}", hit=False)
        stored = self.put(key, value, ttl_s, now)
        return ok(hit=False, value=value) if stored["status"] == "ok" else {**stored, "hit": False}

    def stats(self) -> Dict[str, Any]:
        data = self._state.load()
        return ok(entries=len(data.get("entries", {})), **data.get("stats", {"hits": 0, "misses": 0}))
