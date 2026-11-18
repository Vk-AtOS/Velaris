# ================================================================================

"""Memory drift detector: measures how far new data has moved from a stored baseline, per label.
MemoryDriftDetector.set_baseline(label, data) stores a dict and saves it. get_baseline(label) returns
it or None. drift_score(label, new_data) is the percentage (0-100) of keys, over the union of old and
new keys, whose values differ; with no baseline it returns 100.0, and 0.0 when both are empty.
detect(label, new_data) returns {"label", "score", "status"} with status STABLE below 20, DRIFT below
60, otherwise SEVERE. Plain key-by-key equality, not a statistical test.
State: <VELARIS_DATA>/agents/MEMORY_DRIFT_DETECTOR/baseline.json (owner-only, written atomically by
set_baseline; it does not exist before the first one).
Failure: an unreadable baseline file is logged as a warning and treated as empty; a failed write
raises OSError; non-dict data raises AttributeError.
"""
import json
import logging
import os
from typing import Any, Dict

from velaris.intel.paths import agent_dir, read_private, write_private


logger = logging.getLogger("MEMORY_DRIFT_DETECTOR")

class MemoryDriftDetector:
    """
    Velaris Memory Drift Detector
    - Tracks reference states for components
    - Detects drift between the stored baseline and new data
    - Computes drift magnitude (0–100 scale)
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("MEMORY_DRIFT_DETECTOR"))
        self.BASELINE_PATH = os.path.join(self.AGENT_DIR, "baseline.json")
        self._load()

    def _load(self):
        try:
            self.baseline: Dict[str, Any] = json.loads(read_private(self.BASELINE_PATH)) if os.path.exists(self.BASELINE_PATH) else {}
        except (OSError, ValueError) as e:
            logger.warning("Drift baseline %s is unreadable, starting empty: %s", self.BASELINE_PATH, e)
            self.baseline = {}

    def _save(self):
        write_private(self.BASELINE_PATH, json.dumps(self.baseline, indent=2))      # atomic, owner-only

    def set_baseline(self, label: str, data: Dict[str, Any]):
        self.baseline[label] = data
        self._save()

    def get_baseline(self, label: str) -> Dict[str, Any]:
        return self.baseline.get(label)

    def drift_score(self, label: str, new_data: Dict[str, Any]) -> float:
        old = self.get_baseline(label)
        if old is None:
            return 100.0  # total drift

        drift = 0
        keys = set(list(old.keys()) + list(new_data.keys()))
        total = len(keys)
        if total == 0:
            return 0.0

        for k in keys:
            if old.get(k) != new_data.get(k):
                drift += 1

        return (drift / total) * 100

    def detect(self, label: str, new_data: Dict[str, Any]) -> Dict[str, Any]:
        score = self.drift_score(label, new_data)
        status = "STABLE" if score < 20 else "DRIFT" if score < 60 else "SEVERE"
        return {
            "label": label,
            "score": score,
            "status": status
        }

# ================================================================================