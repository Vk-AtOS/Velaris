# ================================================================================

import os
import json
import time
from typing import Dict, Any, List

class TelemetrySpine:
    """
    Telemetry Spine
    - Central event + metric collector for Velaris
    - Records streams to persistent log
    - Provides query + filter capabilities
    """

    AGENT_DIR = "/live/agents/TELEMETRY_SPINE"
    LOG_PATH = os.path.join(AGENT_DIR, "telemetry.log")

    def __init__(self):
        os.makedirs(self.AGENT_DIR, exist_ok=True)
        if not os.path.exists(self.LOG_PATH):
            with open(self.LOG_PATH, "w") as f:
                f.write("[]")
        self._load_log()

    def _load_log(self):
        try:
            with open(self.LOG_PATH, "r") as f:
                self.events: List[Dict[str, Any]] = json.load(f)
        except:
            self.events = []

    def _save_log(self):
        with open(self.LOG_PATH, "w") as f:
            json.dump(self.events, f, indent=2)

    def record(self, event_type: str, payload: Dict[str, Any]):
        entry = {
            "ts": time.time(),
            "type": event_type,
            "payload": payload
        }
        self.events.append(entry)
        self._save_log()
        return entry

    def query(self, event_type: str = None) -> List[Dict[str, Any]]:
        if event_type is None:
            return list(self.events)
        return [e for e in self.events if e["type"] == event_type]

    def stats(self) -> Dict[str, Any]:
        count = len(self.events)
        groups = {}
        for e in self.events:
            groups[e["type"]] = groups.get(e["type"], 0) + 1
        return {
            "total_events": count,
            "by_type": groups
        }

# ================================================================================