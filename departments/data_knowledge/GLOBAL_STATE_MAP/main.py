"""GLOBAL_STATE_MAP: one shared, versioned map of state that several agents read and write.

Every key has a version that rises by one on each write, and the whole map has
a revision that rises on every change. That gives writers and readers two
guarantees:

  set(key, value, by, expect_version=n)   compare-and-set: the write happens only
                                          if the key is still at version n, so two
                                          agents cannot silently overwrite each other
  changes(since_rev)                      everything that changed after a revision,
                                          in order, so a reader can catch up without
                                          re-reading the map

Each change records who made it. The map and its change log are on disk; the log
keeps the latest MAX_LOG changes.
"""
from __future__ import annotations

import time
from typing import Any, Dict, Optional

from velaris.agentkit.infra_store import State, fail, invalid, is_json, is_name, is_number, ok

NAME = "GLOBAL_STATE_MAP"
MAX_LOG = 2000


class GLOBAL_STATE_MAPAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = State(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def _write(self, key: Any, by: Any, expect_version: Any, value: Any, delete: bool) -> Dict[str, Any]:
        if not isinstance(key, str) or not key or len(key) > 256 or not is_name(by):
            return invalid("key must be a non-empty string and 'by' name the writer")
        if expect_version is not None and (not is_number(expect_version, 0) or isinstance(expect_version, float)):
            return invalid("expect_version must be a whole number >= 0")

        def apply(data: Dict[str, Any]) -> Dict[str, Any]:
            keys = data.setdefault("keys", {})
            current = keys.get(key)
            version = current["version"] if current else 0
            if expect_version is not None and expect_version != version:
                return fail("conflict", f"key is at version {version}, not {expect_version}", version=version)
            if delete and current is None:
                return fail("unknown_key", "no such key")
            data["rev"] = data.get("rev", 0) + 1
            change = {"rev": data["rev"], "key": key, "op": "delete" if delete else "set", "by": by,
                      "ts": time.time(), "version": version + 1}
            if delete:
                del keys[key]
            else:
                keys[key] = {"value": value, "version": version + 1, "rev": data["rev"], "by": by, "ts": change["ts"]}
                change["value"] = value
            data["log"] = (data.get("log", []) + [change])[-MAX_LOG:]
            return ok(key=key, version=version + 1, rev=data["rev"])
        return self._state.change(apply)

    def set(self, key: str, value: Any, by: str, expect_version: Optional[int] = None) -> Dict[str, Any]:
        """Write a key. With expect_version, only if the key is at that version (0 = must not exist yet)."""
        if not is_json(value):
            return invalid("value must be JSON")
        return self._write(key, by, expect_version, value, delete=False)

    def delete(self, key: str, by: str, expect_version: Optional[int] = None) -> Dict[str, Any]:
        return self._write(key, by, expect_version, None, delete=True)

    def get(self, key: str) -> Dict[str, Any]:
        entry = self._state.load().get("keys", {}).get(key) if isinstance(key, str) else None
        return ok(key=key, **entry) if entry else fail("unknown_key", "no such key")

    def snapshot(self) -> Dict[str, Any]:
        data = self._state.load()
        return ok(rev=data.get("rev", 0), state={k: v["value"] for k, v in data.get("keys", {}).items()})

    def changes(self, since_rev: int = 0) -> Dict[str, Any]:
        """Changes with a revision above since_rev, oldest first. `complete` is False if older ones were trimmed."""
        if not is_number(since_rev, 0) or isinstance(since_rev, float):
            return invalid("since_rev must be a whole number >= 0")
        data = self._state.load()
        log = data.get("log", [])
        complete = not log or log[0]["rev"] <= since_rev + 1
        return ok(rev=data.get("rev", 0), changes=[c for c in log if c["rev"] > since_rev], complete=complete)
