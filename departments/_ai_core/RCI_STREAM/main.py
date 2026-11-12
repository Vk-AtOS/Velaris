"""RCI_STREAM: durable, append-only event streams with offsets.

RCI is read here as "running context ingestion": events arrive on a topic
(RCI_STREAM), a bounded context is built from the latest of them
(RCI_CONTEXT), and RCI_CORE screens events on the way in.

publish(topic, event) appends one JSON line to the topic's owner-only file
under this agent's state directory and returns the event's offset (1, 2, ...).
read(topic, after=n) returns events with a higher offset, so a reader that
remembers its last offset never misses or repeats an event, across restarts.
ponytail: one file per topic, read in full; add segment files and an index
when a topic passes a few hundred thousand events.
"""
import logging
import re
import threading
import time
from typing import Any, Dict, List

from velaris.agentkit.checks import is_json
from velaris.agentkit.results import fail, health, invalid
from velaris.agentkit.state import append_line, peek_dir, read_lines
from velaris.intel.paths import agent_dir

logger = logging.getLogger("RCI_STREAM")
NAME = "RCI_STREAM"
_TOPIC = re.compile(r"^[a-z0-9][a-z0-9_.-]{0,63}$")
MAX_READ = 1000
_publish_lock = threading.Lock()      # offset = count + 1 must not interleave with another append


class RCI_STREAMAgent:
    def health_check(self):
        return health(NAME)

    def publish(self, topic: str, event: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(topic, str) or not _TOPIC.match(topic):
            return invalid("topic must be 1-64 characters of a-z, 0-9, '_', '.', '-'")
        if not isinstance(event, dict) or not event or not is_json(event):
            return invalid("event must be a non-empty JSON object")
        try:
            with _publish_lock:
                offset = len(read_lines(peek_dir(NAME) / f"{topic}.jsonl")) + 1
                entry = {"offset": offset, "ts": time.time(), "event": event}
                append_line(agent_dir(NAME) / f"{topic}.jsonl", entry)
        except OSError as e:
            logger.warning("RCI_STREAM could not append to %s: %s", topic, e)
            return fail("storage_error", "the event could not be stored")
        return {"status": "ok", "topic": topic, "offset": offset, "ts": entry["ts"]}

    def read(self, topic: str, after: int = 0, limit: int = 100) -> Dict[str, Any]:
        """Events with offset > after, oldest first, at most `limit`."""
        if not isinstance(topic, str) or not _TOPIC.match(topic):
            return invalid("unknown topic name", events=[])
        if any(not isinstance(n, int) or isinstance(n, bool) for n in (after, limit)) \
                or after < 0 or not 1 <= limit <= MAX_READ:
            return invalid(f"after must be >= 0 and limit 1..{MAX_READ}", events=[])
        entries = read_lines(peek_dir(NAME) / f"{topic}.jsonl")
        batch = [e for e in entries if e.get("offset", 0) > after][:limit]
        return {"status": "ok", "topic": topic, "events": batch, "last_offset": len(entries),
                "next_after": batch[-1]["offset"] if batch else after}

    def topics(self) -> List[str]:
        folder = peek_dir(NAME)
        return sorted(p.stem for p in folder.glob("*.jsonl")) if folder.exists() else []
