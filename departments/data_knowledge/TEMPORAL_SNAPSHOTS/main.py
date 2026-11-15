# ================================================================================

"""Temporal snapshots: stores labelled, timestamped copies of any JSON-serialisable data and retrieves or compares them.

TemporalSnapshots(): create_snapshot(label, data) appends {label, timestamp, data} and
returns it (labels are not required to be unique); list_snapshots() returns labels;
restore(label) returns the data of the first snapshot with that label; compare(a, b)
returns {"a", "b", "equal"} using the last snapshot matching each label.
State: snapshots.json under velaris.intel.paths.agent_dir("TEMPORAL_SNAPSHOTS") (honours
VELARIS_DATA), rewritten in full on every create; created as [] if missing.
Failure: an unreadable or corrupt file is logged and treated as empty; restore returns
None for an unknown label and compare gives None for it; non-serialisable data raises
TypeError on save.
"""

import logging
import os
import time
from typing import Dict, Any, List

from velaris.agentkit.state import JsonState
from velaris.intel.paths import agent_dir

logger = logging.getLogger("TEMPORAL_SNAPSHOTS")
MAX_SNAPSHOTS = 500


class TemporalSnapshots:
    """
    Velaris Temporal Snapshots
    - Stores timestamped snapshots of any data structure (owner-only file, atomic and locked across workers)
    - Allows restoring, listing, and comparing snapshots
    - A label used twice keeps both snapshots; restore and compare always use the NEWEST one
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("TEMPORAL_SNAPSHOTS"))
        self.SNAP_PATH = os.path.join(self.AGENT_DIR, "snapshots.json")
        self._state = JsonState("TEMPORAL_SNAPSHOTS", path=self.SNAP_PATH)

    @property
    def snaps(self) -> List[Dict[str, Any]]:
        return list(self._state.load().get("snaps", []))

    def create_snapshot(self, label: str, data: Any) -> Dict[str, Any]:
        snap = {
            "label": label,
            "timestamp": time.time(),
            "data": data
        }
        self._state.update(lambda d: d.__setitem__("snaps", (d.get("snaps", []) + [snap])[-MAX_SNAPSHOTS:]))
        return snap

    def list_snapshots(self) -> List[str]:
        return [s["label"] for s in self.snaps]

    def _newest(self, label: str):
        """(found, data) of the newest snapshot with this label."""
        for s in reversed(self.snaps):
            if s["label"] == label:
                return True, s["data"]
        return False, None

    def restore(self, label: str) -> Any:
        return self._newest(label)[1]

    def compare(self, a: str, b: str) -> Dict[str, Any]:
        found_a, da = self._newest(a)
        found_b, db = self._newest(b)
        # Two unknown labels are not "equal": nothing was compared.
        return {"a": da, "b": db, "found": {"a": found_a, "b": found_b},
                "equal": (da == db) if found_a and found_b else None}

# ================================================================================
