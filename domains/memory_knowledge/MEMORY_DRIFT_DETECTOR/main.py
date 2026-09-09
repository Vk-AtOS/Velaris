# ================================================================================

import json
import os
from typing import Any, Dict


class MemoryDriftDetector:
    """
    Velaris Memory Drift Detector
    - Tracks reference states for components
    - Detects drift between the stored baseline and new data
    - Computes drift magnitude (0–100 scale)
    """

    AGENT_DIR = "/live/agents/MEMORY_DRIFT_DETECTOR"
    BASELINE_PATH = os.path.join(AGENT_DIR, "baseline.json")

    def __init__(self):
        os.makedirs(self.AGENT_DIR, exist_ok=True)
        if not os.path.exists(self.BASELINE_PATH):
            with open(self.BASELINE_PATH, "w") as f:
                f.write("{}")
        self._load()

    def _load(self):
        try:
            with open(self.BASELINE_PATH, "r") as f:
                self.baseline: Dict[str, Any] = json.load(f)
        except:
            self.baseline = {}

    def _save(self):
        with open(self.BASELINE_PATH, "w") as f:
            json.dump(self.baseline, f, indent=2)

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