# ================================================================================

"""Autonomous patch engine: applies a JSON patch (a dict of field changes) to a dict and records it in a history.

validate_patch(patch) is True only when the patch has "target" and a dict "changes". simulate_patch(original, patch)
returns a copy of original with the changes overlaid (no validation, so a patch without "changes" raises KeyError).
apply_patch(original, patch) validates, then returns the updated copy and appends {"patch", "status": "APPLIED"} to the
history; an invalid patch raises ValueError. It never edits any module or file named by "target". get_history() returns a copy.
State: <VELARIS_DATA>/agents/AUTONOMOUS_PATCH_ENGINE/patch_history.json (created as [] on start; an unreadable file is
logged and the history starts empty, and the next apply overwrites it). Write errors (OSError) propagate.
"""
import logging
import os
import json
from typing import Dict, List, Any

from velaris.intel.paths import agent_dir

logger = logging.getLogger("AUTONOMOUS_PATCH_ENGINE")

class AutonomousPatchEngine:
    """
    Velaris Autonomous Patch Engine
    - Applies offline-safe JSON-based patches to internal modules
    - Stores patch history
    - Validates and simulates patches before applying
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("AUTONOMOUS_PATCH_ENGINE"))
        self.PATCH_LOG = os.path.join(self.AGENT_DIR, "patch_history.json")
        if not os.path.exists(self.PATCH_LOG):
            with open(self.PATCH_LOG, "w") as f:
                f.write("[]")
        self._load_log()

    def _load_log(self):
        try:
            with open(self.PATCH_LOG, "r") as f:
                self.history = json.load(f)
        except (OSError, ValueError) as e:
            logger.warning("Patch history %s is unreadable, starting empty: %s", self.PATCH_LOG, e)
            self.history = []

    def _save_log(self):
        with open(self.PATCH_LOG, "w") as f:
            json.dump(self.history, f, indent=2)

    def validate_patch(self, patch: Dict[str, Any]) -> bool:
        # A valid patch must contain a target and changes
        if "target" not in patch or "changes" not in patch:
            return False
        if not isinstance(patch["changes"], dict):
            return False
        return True

    def simulate_patch(self, original: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(original)
        for k, v in patch["changes"].items():
            result[k] = v
        return result

    def apply_patch(self, original: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        if not self.validate_patch(patch):
            raise ValueError("Invalid patch structure")

        updated = self.simulate_patch(original, patch)
        self.history.append({"patch": patch, "status": "APPLIED"})
        self._save_log()
        return updated

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.history)

# ================================================================================