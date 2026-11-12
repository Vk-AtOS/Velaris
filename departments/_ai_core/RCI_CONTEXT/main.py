"""RCI_CONTEXT: builds a bounded "current context" from a stream of events.

build(entries) folds stream entries ({"offset", "ts", "event"}) into
  facts   the latest value of every key seen (newer events overwrite older),
          with the offset each value came from
  recent  the last `max_events` events
and then drops the oldest recent events until the whole context fits
`max_chars` of JSON, so it can be put in front of a model without overflowing
it. Events older than `ttl_seconds` are ignored. snapshot(topic) does the
same for a topic held by RCI_STREAM. Nothing is stored here: the stream is the state.
"""
import json
import time
from typing import Any, Dict, List, Optional

from velaris.agentkit.aicore_b_common import health, invalid, number
from velaris.agents.RCI_STREAM.main import MAX_READ, RCI_STREAMAgent

NAME = "RCI_CONTEXT"


class RCI_CONTEXTAgent:
    def __init__(self):
        self.stream = RCI_STREAMAgent()

    def health_check(self):
        return health(NAME)

    def build(self, entries: Any, max_events: int = 20, max_chars: int = 4000,
              ttl_seconds: Optional[float] = None, now: Optional[float] = None) -> Dict[str, Any]:
        if not isinstance(entries, list) or not all(isinstance(e, dict) and isinstance(e.get("event"), dict)
                                                    for e in entries):
            return invalid("entries must be a list of {'offset', 'ts', 'event': {...}}", facts={}, recent=[])
        if not isinstance(max_events, int) or max_events < 1 or not isinstance(max_chars, int) or max_chars < 2:
            return invalid("max_events must be >= 1 and max_chars >= 2", facts={}, recent=[])
        if ttl_seconds is not None and (number(ttl_seconds) is None or ttl_seconds <= 0):
            return invalid("ttl_seconds must be a positive number", facts={}, recent=[])
        now = time.time() if now is None else now
        live = [e for e in entries
                if ttl_seconds is None or now - (number(e.get("ts")) or 0.0) <= ttl_seconds]
        live.sort(key=lambda e: e.get("offset", 0))
        facts: Dict[str, Any] = {}
        fact_offsets: Dict[str, Any] = {}
        for e in live:
            for key, value in e["event"].items():
                facts[key], fact_offsets[key] = value, e.get("offset")
        recent: List[Dict[str, Any]] = [e["event"] for e in live[-max_events:]]
        dropped = 0
        while recent and len(json.dumps({"facts": facts, "recent": recent}, default=str)) > max_chars:
            recent.pop(0)
            dropped += 1
        size = len(json.dumps({"facts": facts, "recent": recent}, default=str))
        return {"status": "ok" if size <= max_chars else "over_budget", "facts": facts,
                "fact_offsets": fact_offsets, "recent": recent, "events_used": len(live),
                "expired": len(entries) - len(live), "trimmed": dropped, "chars": size,
                "last_offset": live[-1].get("offset") if live else None}

    def snapshot(self, topic: str, **options: Any) -> Dict[str, Any]:
        """The context of a topic in RCI_STREAM. Options are those of build()."""
        entries, after = [], 0
        while True:
            page = self.stream.read(topic, after=after, limit=MAX_READ)
            if page["status"] != "ok":
                return {**page, "facts": {}, "recent": []}
            entries += page["events"]
            if len(page["events"]) < MAX_READ:
                break
            after = page["next_after"]
        try:
            return {**self.build(entries, **options), "topic": topic}
        except TypeError as e:
            return invalid(f"unknown option: {e}", facts={}, recent=[])
