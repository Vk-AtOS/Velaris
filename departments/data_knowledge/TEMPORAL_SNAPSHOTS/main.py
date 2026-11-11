# ================================================================================

import os
import json
import time
from typing import Dict, Any, List

from velaris.intel.paths import agent_dir


class TemporalSnapshots:
    """
    Velaris Temporal Snapshots
    - Stores timestamped snapshots of any data structure
    - Allows restoring, listing, and comparing snapshots
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("TEMPORAL_SNAPSHOTS"))
        self.SNAP_PATH = os.path.join(self.AGENT_DIR, "snapshots.json")
        if not os.path.exists(self.SNAP_PATH):
            with open(self.SNAP_PATH, "w") as f:
                f.write("[]")
        self._load()

    def _load(self):
        try:
            with open(self.SNAP_PATH, "r") as f:
                self.snaps: List[Dict[str, Any]] = json.load(f)
        except:
            self.snaps = []

    def _save(self):
        with open(self.SNAP_PATH, "w") as f:
            json.dump(self.snaps, f, indent=2)

    def create_snapshot(self, label: str, data: Any) -> Dict[str, Any]:
        snap = {
            "label": label,
            "timestamp": time.time(),
            "data": data
        }
        self.snaps.append(snap)
        self._save()
        return snap

    def list_snapshots(self) -> List[str]:
        return [s["label"] for s in self.snaps]

    def restore(self, label: str) -> Any:
        for s in self.snaps:
            if s["label"] == label:
                return s["data"]
        return None

    def compare(self, a: str, b: str) -> Dict[str, Any]:
        da = None
        db = None
        for s in self.snaps:
            if s["label"] == a:
                da = s["data"]
            if s["label"] == b:
                db = s["data"]
        return {"a": da, "b": db, "equal": da == db}

# ================================================================================