"""Autonomous patch engine: overlays a JSON patch (a dict of field changes) on a dict and keeps an audit history.

validate_patch(patch) is True only when the patch has a text "target" and a dict "changes" (at most 200 keys, all text,
JSON values). simulate_patch(original, patch) returns a copy of original with the changes overlaid; an invalid patch
raises ValueError. apply_patch(original, patch) needs an authenticated caller (PermissionError otherwise), validates,
and returns the updated COPY; it records {"patch", "status": "COMPUTED", "by", "ts", "before", "after"} (sha256 of the
original and of the result). The status is COMPUTED, not APPLIED, because this engine never edits any module, file or
store named by "target": whoever calls it decides what to do with the returned copy. get_history() returns a copy.
State: <VELARIS_DATA>/agents/AUTONOMOUS_PATCH_ENGINE/patch_history.json (JsonState: owner-only, atomic, shared by all
workers, the newest 1,000 entries). Write errors (OSError) propagate.
"""
import hashlib
import json
import logging
import os
import time
from typing import Dict, List, Any

from velaris.agentkit.state import JsonState
from velaris.core.access import check_caller
from velaris.intel.paths import agent_dir

logger = logging.getLogger("AUTONOMOUS_PATCH_ENGINE")
NAME = "AUTONOMOUS_PATCH_ENGINE"
MAX_ENTRIES = 1000
MAX_CHANGES = 200


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


class AutonomousPatchEngine:
    """
    Velaris Autonomous Patch Engine
    - Computes the result of offline JSON patches and records who asked for what
    - Stores patch history
    - Validates and simulates patches before computing
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir(NAME))
        self.PATCH_LOG = os.path.join(self.AGENT_DIR, "patch_history.json")
        self._state = JsonState(NAME, path=self.PATCH_LOG, default={"history": []})

    @property
    def history(self) -> List[Dict[str, Any]]:
        return list(self._state.load().get("history") or [])

    def validate_patch(self, patch: Dict[str, Any]) -> bool:
        if not isinstance(patch, dict) or not isinstance(patch.get("target"), str) or not patch["target"].strip():
            return False
        changes = patch.get("changes")
        if not isinstance(changes, dict) or len(changes) > MAX_CHANGES or not all(isinstance(k, str) for k in changes):
            return False
        try:
            json.dumps(changes)
        except (TypeError, ValueError):
            return False
        return True

    def simulate_patch(self, original: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(original, dict) or not self.validate_patch(patch):
            raise ValueError("Invalid patch structure")
        return {**original, **patch["changes"]}

    def apply_patch(self, original: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
        who, refused = check_caller(NAME, "apply_patch", {"target": str((patch or {}).get("target"))[:128]
                                                          if isinstance(patch, dict) else None})
        if refused:
            raise PermissionError(refused.get("reason", "not allowed"))
        updated = self.simulate_patch(original, patch)
        entry = {"patch": patch, "status": "COMPUTED", "by": who.id, "ts": time.time(),
                 "before": _sha(original), "after": _sha(updated)}

        def add(d):
            d.setdefault("history", []).append(entry)
            del d["history"][:-MAX_ENTRIES]
        self._state.update(add)
        return updated

    def get_history(self) -> List[Dict[str, Any]]:
        return self.history
