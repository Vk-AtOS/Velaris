"""INTER_AGENT_COHESION: a shared board where agents leave facts for each other without overwriting each other.

link(namespace, key, value, ttl, agent, expected_version) stores a value with
a version number, the writing agent and an optional expiry. When
expected_version is given the write succeeds only if the stored version still
is that number (compare-and-set), so two agents updating the same fact cannot
silently lose each other's change: the second gets "conflict" and the current
value. recall / list_namespace read current, unexpired values. Stored
owner-only under this agent's state directory; survives restart.
"""
import time
from typing import Any, Dict, Optional

from velaris.agentkit.checks import ident, is_json, number
from velaris.agentkit.results import fail, health, invalid
from velaris.agentkit.state import JsonState

NAME = "INTER_AGENT_COHESION"


def _alive(entry: Dict[str, Any], now: float) -> bool:
    return entry.get("expires") is None or now < entry["expires"]


class Cohesion:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "1.0.0")
        self._board = JsonState(NAME, "board.json", {"spaces": {}})

    def health_check(self):
        return {**health(NAME), "version": self.version}

    def link(self, namespace: str, key: str, metadata: Any, ttl: Optional[float] = None, agent: str = "unknown",
             expected_version: Optional[int] = None) -> Dict[str, Any]:
        """Store `metadata` under namespace/key. Returns the new version, or "conflict" with the current entry."""
        if ident(namespace, 100) is None or ident(key, 200) is None or not is_json(metadata):
            return invalid("namespace and key must be names and the value JSON")
        if ttl is not None and (number(ttl) is None or ttl <= 0):
            return invalid("ttl must be a positive number of seconds")
        if expected_version is not None and (not isinstance(expected_version, int) or isinstance(expected_version, bool)):
            return invalid("expected_version must be an integer")
        now = time.time()

        def change(state):
            space = state.setdefault("spaces", {}).setdefault(namespace, {})
            old = space.get(key)
            current = old["version"] if old and _alive(old, now) else 0
            if expected_version is not None and expected_version != current:
                return fail("conflict", f"{namespace}/{key} is at version {current}, not {expected_version}",
                            current={k: old[k] for k in ("value", "version", "agent")} if current else None)
            space[key] = {"value": metadata, "version": current + 1, "agent": agent, "ts": now,
                          "expires": now + ttl if ttl is not None else None}
            return {"status": "ok", "version": current + 1}
        return self._board.update(change)

    def entry(self, namespace: str, key: str) -> Optional[Dict[str, Any]]:
        """Value with its version, writer and time, or None."""
        e = self._board.load().get("spaces", {}).get(namespace, {}).get(key)
        return e if e and _alive(e, time.time()) else None

    def recall(self, namespace: str, key: str):
        e = self.entry(namespace, key)
        return e["value"] if e else None

    def list_namespace(self, namespace: str, prefix: Optional[str] = None) -> Dict[str, Any]:
        now = time.time()
        space = self._board.load().get("spaces", {}).get(namespace, {})
        return {k: e["value"] for k, e in sorted(space.items())
                if _alive(e, now) and (prefix is None or k.startswith(prefix))}
