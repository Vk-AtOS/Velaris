"""SHORTTERM_MEMORY: bounded working memory per session.

push() appends an item to a session; only the newest `capacity` items are kept
and an item may carry a time-to-live. recent() returns what is still alive,
oldest first. The buffer is on disk, so a restart mid-conversation loses nothing.

promote() is the hand-over to long-term memory: the session's text goes to
velaris.intel.memory (via LONGTERM_MEMORY's store), which extracts durable
facts, masks secrets and supersedes outdated ones. This agent decides nothing
about what is worth keeping for good.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from velaris.agentkit import infra_memory
from velaris.agentkit.checks import is_json, is_name, is_number
from velaris.agentkit.results import invalid, ok
from velaris.agentkit.state import JsonState

NAME = "SHORTTERM_MEMORY"
MAX_CAPACITY = 10000


class SHORTTERM_MEMORYAgent:
    def __init__(self, capacity: int = 100) -> None:
        self.name = NAME
        valid = is_number(capacity, 1, MAX_CAPACITY) and not isinstance(capacity, float)
        self.capacity = capacity if valid else 100
        self.llm = None                 # optional velaris.intel.llm.LLM used by promote()
        self._state = JsonState(NAME, encrypted="memory:SHORTTERM_MEMORY")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def push(self, item: Any, session: str = "default", ttl_s: Optional[float] = None,
             now: Optional[float] = None) -> Dict[str, Any]:
        if not is_name(session) or not is_json(item):
            return invalid("session must be a short name and item a JSON value")
        if (ttl_s is not None and not is_number(ttl_s, 0.001)) or (now is not None and not is_number(now, 0)):
            return invalid("ttl_s must be a positive number and now a timestamp")
        now = time.time() if now is None else now
        entry = {"item": item, "ts": now, "expires": None if ttl_s is None else now + ttl_s}

        def add(data: Dict[str, Any]) -> int:
            sessions = data.setdefault("sessions", {})
            sessions[session] = (sessions.get(session, []) + [entry])[-self.capacity:]
            return len(sessions[session])
        return ok(session=session, size=self._state.update(add))

    def _alive(self, session: Any, now: Optional[float]) -> List[Dict[str, Any]]:
        now = time.time() if not is_number(now, 0) else now
        entries = self._state.load().get("sessions", {}).get(session, []) if isinstance(session, str) else []
        return [e for e in entries if e["expires"] is None or e["expires"] > now]

    def recent(self, n: int = 10, session: str = "default", now: Optional[float] = None) -> List[Any]:
        """The newest n live items of a session, oldest first ([] for an unknown session or a bad n)."""
        if not is_number(n, 1) or isinstance(n, float):
            return []
        return [e["item"] for e in self._alive(session, now)][-n:]

    def clear(self, session: str = "default") -> Dict[str, Any]:
        dropped = self._state.update(lambda d: len(d.get("sessions", {}).pop(session, []))
                                     if isinstance(session, str) else 0)
        return ok(session=session, dropped=dropped)

    def promote(self, session: str, scope: str, source: str = "", now: Optional[float] = None) -> Dict[str, Any]:
        """Send a session's text (strings, or the "text" of objects) to long-term memory under `scope`."""
        if not isinstance(source, str):
            return invalid("source must be text")
        items = [e["item"] for e in self._alive(session, now)]
        texts = [i if isinstance(i, str) else i.get("text") for i in items if isinstance(i, (str, dict))]
        return infra_memory.remember(self.llm, texts, scope, source or f"shortterm:{session}")
