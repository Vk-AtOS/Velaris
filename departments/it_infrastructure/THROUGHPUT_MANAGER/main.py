"""THROUGHPUT_MANAGER: token-bucket rate limits.

Each key (a tenant, an API, an agent) has a bucket that refills at `rate_per_s`
tokens per second up to `burst`. acquire() takes tokens if they are there and
otherwise refuses, saying how long until enough will have refilled:

    tokens      = min(burst, tokens + (now - last) * rate_per_s)
    retry_after = (wanted - tokens) / rate_per_s

A key with no limit set is refused: an unlimited caller has to be declared, not
assumed. Buckets and counters persist, so a restart does not hand out a fresh burst.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from velaris.agentkit.infra_store import State, fail, invalid, is_name, is_number, ok

NAME = "THROUGHPUT_MANAGER"


class THROUGHPUT_MANAGERAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = State(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def set_limit(self, key: str, rate_per_s: float, burst: float) -> Dict[str, Any]:
        if not is_name(key) or not is_number(rate_per_s, 0.000001) or not is_number(burst, 1):
            return invalid("need a key name, rate_per_s > 0 and burst >= 1")

        def put(data: Dict[str, Any]) -> None:
            b = data.setdefault("buckets", {}).setdefault(key, {"tokens": burst, "last": None, "allowed": 0, "refused": 0})
            b.update(rate=rate_per_s, burst=burst, tokens=min(b["tokens"], burst))
        self._state.change(put)
        return ok(key=key, rate_per_s=rate_per_s, burst=burst)

    def acquire(self, key: str, tokens: float = 1.0, now: Optional[float] = None) -> Dict[str, Any]:
        if not is_number(tokens) or tokens <= 0:
            return invalid("tokens must be a number > 0", allowed=False)
        if now is not None and not is_number(now, 0):
            return invalid("now must be a timestamp", allowed=False)
        now = time.time() if now is None else now

        def take(data: Dict[str, Any]) -> Dict[str, Any]:
            b = data.get("buckets", {}).get(key) if isinstance(key, str) else None
            if b is None:
                return fail("no_limit", "set_limit() has not been called for this key", allowed=False)
            if tokens > b["burst"]:
                return fail("denied", f"{tokens} tokens can never fit a burst of {b['burst']}", allowed=False)
            elapsed = max(0.0, now - (b["last"] if b["last"] is not None else now))   # a clock that went back refills nothing
            b["tokens"], b["last"] = min(b["burst"], b["tokens"] + elapsed * b["rate"]), now
            if tokens <= b["tokens"]:
                b["tokens"] -= tokens
                b["allowed"] += 1
                return ok(allowed=True, remaining=round(b["tokens"], 6), retry_after_s=0.0)
            b["refused"] += 1
            return fail("rate_limited", "bucket is empty", allowed=False, remaining=round(b["tokens"], 6),
                        retry_after_s=round((tokens - b["tokens"]) / b["rate"], 6))
        return self._state.change(take)

    def stats(self, key: str) -> Dict[str, Any]:
        b = self._state.load().get("buckets", {}).get(key) if isinstance(key, str) else None
        if b is None:
            return fail("no_limit", "no such key")
        return ok(key=key, allowed=b["allowed"], refused=b["refused"], tokens=round(b["tokens"], 6),
                  rate_per_s=b["rate"], burst=b["burst"])
