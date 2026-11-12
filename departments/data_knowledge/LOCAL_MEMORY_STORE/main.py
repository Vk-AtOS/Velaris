"""LOCAL_MEMORY_STORE: a small key-value store on this machine's disk.

put / get / delete / keys over one JSON file, written atomically and readable
by its owner only. A value may carry a time-to-live, after which get() no longer
returns it. The file lives in the agent's private data directory unless the
caller names a path.

It is a plain local store: no search, no versions, no scopes. Facts worth
recalling by meaning belong in LONGTERM_MEMORY.
"""
from __future__ import annotations

import time

from velaris.agentkit import infra_store

_NAME = "LOCAL_MEMORY_STORE"


class LocalMemoryStore:
    def __init__(self, path=None):
        self.name = _NAME
        self.path = path if isinstance(path, str) and path else None
        self._state = infra_store.State(_NAME, "store.json", path=self.path)

    def health_check(self):
        return {"agent": _NAME, "status": "ok", "version": "1.0.0"}

    def put(self, k, v, ttl_s=None, now=None):
        if not isinstance(k, str) or not k or len(k) > 512 or not infra_store.is_json(v):
            return infra_store.invalid("key must be a non-empty string and value JSON")
        if (ttl_s is not None and not infra_store.is_number(ttl_s, 0.001)) or (
                now is not None and not infra_store.is_number(now, 0)):
            return infra_store.invalid("ttl_s must be a positive number and now a timestamp")
        now = time.time() if now is None else now
        entry = {"value": v, "expires": None if ttl_s is None else now + ttl_s}
        self._state.change(lambda d: d.__setitem__(k, entry))
        return infra_store.ok(key=k)

    def _live(self, now):
        now = time.time() if not infra_store.is_number(now, 0) else now
        return {k: e["value"] for k, e in self._state.load().items()
                if isinstance(e, dict) and "value" in e and (e.get("expires") is None or e["expires"] > now)}

    def get(self, k, default=None, now=None):
        """The stored value, or `default` if the key is absent, expired or not a string."""
        return self._live(now).get(k, default) if isinstance(k, str) else default

    def delete(self, k):
        gone = self._state.change(lambda d: d.pop(k, None) is not None) if isinstance(k, str) else False
        return infra_store.ok(key=k) if gone else infra_store.fail("unknown_key", "no such key")

    def keys(self, prefix="", now=None):
        return sorted(k for k in self._live(now) if isinstance(prefix, str) and k.startswith(prefix))
