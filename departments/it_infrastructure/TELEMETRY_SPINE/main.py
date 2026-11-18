# ================================================================================

"""Telemetry spine: an append-only local log of typed events with a simple query and per-type counts.

record(event_type, payload) appends {"ts", "type", "payload"} as one JSON line and returns the entry; the payload is
first redacted of secrets and personal identifiers (velaris.agentkit.infra_store.redact_json). It returns None and writes
nothing when event_type is not a plain name, the payload is not a JSON-serialisable dict, or the entry is over 16 KiB.
query(event_type=None) returns the newest 10,000 events, optionally of one type; stats() counts them by type.
State: <VELARIS_DATA>/agents/TELEMETRY_SPINE/telemetry.jsonl, owner-only and locked across workers. Beyond 20 MiB the
file is renamed to telemetry.jsonl.1 (one generation kept) and a new one starts, so older events leave query(). A torn
last line is skipped on read. No caller check is made.
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, Any, List

from velaris.agentkit.checks import is_json, is_name
from velaris.agentkit.infra_store import redact_json
from velaris.agentkit.state import append_line, read_tail
from velaris.core.filelock import lock_for
from velaris.intel.paths import agent_dir

logger = logging.getLogger("TELEMETRY_SPINE")
MAX_EVENT_BYTES = 16 * 1024          # one event
MAX_LOG_BYTES = 20 * 1024 * 1024     # the log rotates to telemetry.log.1 beyond this (one generation kept)
MAX_QUERY = 10_000                   # newest events returned by query()


class TelemetrySpine:
    """
    Telemetry Spine
    - Central event + metric collector for Velaris
    - Appends one JSON line per event (owner-only, locked across workers, a bad payload cannot damage
      earlier events); payloads are redacted of secrets and personal identifiers and size-bounded
    - Provides query + filter capabilities over the newest events
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("TELEMETRY_SPINE"))
        self.LOG_PATH = os.path.join(self.AGENT_DIR, "telemetry.jsonl")
        self._path = Path(self.LOG_PATH)

    @property
    def events(self) -> List[Dict[str, Any]]:
        return read_tail(self._path, MAX_QUERY)

    def record(self, event_type: str, payload: Dict[str, Any]):
        """The stored entry, or None when the event is not a name plus a JSON object of reasonable size."""
        if not is_name(event_type) or not isinstance(payload, dict) or not is_json(payload):
            logger.warning("TELEMETRY_SPINE refused an event that is not a type name and a JSON object")
            return None
        entry = {"ts": time.time(), "type": event_type, "payload": redact_json(payload)}
        if len(json.dumps(entry)) > MAX_EVENT_BYTES:
            logger.warning("TELEMETRY_SPINE refused a %s event over %d bytes", event_type, MAX_EVENT_BYTES)
            return None
        with lock_for(self.LOG_PATH + ".lock"):
            if os.path.exists(self.LOG_PATH) and os.path.getsize(self.LOG_PATH) > MAX_LOG_BYTES:
                os.replace(self.LOG_PATH, self.LOG_PATH + ".1")
            append_line(self._path, entry)
        return entry

    def query(self, event_type: str = None) -> List[Dict[str, Any]]:
        if event_type is None:
            return list(self.events)
        return [e for e in self.events if e["type"] == event_type]

    def stats(self) -> Dict[str, Any]:
        events = self.events
        groups = {}
        for e in events:
            groups[e["type"]] = groups.get(e["type"], 0) + 1
        return {
            "total_events": len(events),
            "by_type": groups
        }

# ================================================================================
