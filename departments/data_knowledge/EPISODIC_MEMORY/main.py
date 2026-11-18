"""EPISODIC_MEMORY: a durable, time-ordered log of what happened.

An episode is one event described by the caller: who did what, with what
outcome ({"actor": ..., "summary": ..., "tags": [...], ...}). record() stamps it
with an id and a time and masks secrets and personal identifiers in its text
(velaris.intel.guard) before it is written. list_episodes() answers "what
happened between these times / by this actor / with this tag".

consolidate() hands the summaries of episodes not yet consolidated to long-term
memory (velaris.intel.memory), which turns them into durable facts. The episode file is locked only to claim the
episodes (for CLAIM_SECONDS, so a second consolidate skips them) and again to mark them done, never while the model
runs, so record() is not blocked by a slow consolidation; a failed consolidation releases its claim. Episodes
themselves are never edited or deleted; only the oldest fall off after MAX_EPISODES.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from velaris.agentkit import infra_memory
from velaris.agentkit.checks import is_json, is_number
from velaris.agentkit.results import invalid, ok
from velaris.agentkit.state import JsonState
from velaris.agentkit.infra_store import redact_json

NAME = "EPISODIC_MEMORY"
MAX_EPISODES = 5000
CLAIM_SECONDS = 600


class EPISODIC_MEMORYAgent:
    def __init__(self) -> None:
        self.name = NAME
        self.llm = None                 # optional velaris.intel.llm.LLM used by consolidate()
        self._state = JsonState(NAME, "episodes.json", encrypted="memory:EPISODIC_MEMORY")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def record(self, episode: dict, now: Optional[float] = None) -> Dict[str, Any]:
        if not isinstance(episode, dict) or not episode or not is_json(episode):
            return invalid("episode must be a non-empty JSON object")
        if now is not None and not is_number(now, 0):
            return invalid("now must be a timestamp")
        stored = {**redact_json(episode), "_id": uuid.uuid4().hex, "_ts": time.time() if now is None else now,
                  "_consolidated": False}
        self._state.update(lambda d: d.__setitem__("episodes", (d.get("episodes", []) + [stored])[-MAX_EPISODES:]))
        return ok(id=stored["_id"], ts=stored["_ts"])

    def list_episodes(self, since: Optional[float] = None, until: Optional[float] = None,
                      actor: Optional[str] = None, tag: Optional[str] = None,
                      limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Episodes in time order, filtered. `since` is inclusive, `until` exclusive; limit keeps the newest."""
        out = sorted(self._state.load().get("episodes", []), key=lambda e: e["_ts"])
        if is_number(since):
            out = [e for e in out if e["_ts"] >= since]
        if is_number(until):
            out = [e for e in out if e["_ts"] < until]
        if actor is not None:
            out = [e for e in out if e.get("actor") == actor]
        if tag is not None:
            out = [e for e in out if isinstance(e.get("tags"), list) and tag in e["tags"]]
        return out[-limit:] if is_number(limit, 1) and not isinstance(limit, float) else out

    def consolidate(self, scope: str, source: str = "episodic") -> Dict[str, Any]:
        """Turn the "summary" of each not-yet-consolidated episode into long-term facts under `scope`."""
        if not isinstance(source, str):
            return invalid("source must be text")
        now = time.time()
        claim = uuid.uuid4().hex

        def take(data):
            todo = [e for e in data.get("episodes", []) if not e["_consolidated"] and isinstance(e.get("summary"), str)
                    and e["summary"].strip() and now - e.get("_claimed_at", 0) > CLAIM_SECONDS]
            for e in todo:
                e["_claim"], e["_claimed_at"] = claim, now
            return [(e["_id"], e["summary"]) for e in todo]
        todo = self._state.update(take)
        if not todo:
            return {"status": "nothing_to_store", "facts": [], "counts": {}, "episodes": 0}
        try:
            result = infra_memory.remember(self.llm, [t for _, t in todo], scope, source)      # slow: no lock held
        except BaseException:
            self._finish(claim, done=False)
            raise
        self._finish(claim, done=result["status"] == "ok")
        return {**result, "episodes": len(todo)}

    def _finish(self, claim: str, done: bool) -> None:
        def mark(data):
            for e in data.get("episodes", []):
                if e.get("_claim") == claim:
                    e["_consolidated"] = e["_consolidated"] or done
                    e.pop("_claim", None)
                    e.pop("_claimed_at", None)
        self._state.update(mark)
