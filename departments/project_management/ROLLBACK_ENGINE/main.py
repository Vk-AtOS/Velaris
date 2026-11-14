# ================================================================================

import json
import logging
import os
import re
from typing import List, Dict, Any

from velaris.intel.paths import agent_dir

logger = logging.getLogger("ROLLBACK_ENGINE")
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")

class RollbackEngine:
    """
    Velaris Rollback Engine
    - Stores snapshots of system state
    - Allows reverting to any previous snapshot
    - Maintains a rollback history log
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("ROLLBACK_ENGINE"))
        self.SNAPSHOT_DIR = os.path.join(self.AGENT_DIR, "snapshots")
        self.LOG_PATH = os.path.join(self.AGENT_DIR, "rollback.log")
        os.makedirs(self.SNAPSHOT_DIR, exist_ok=True)
        if not os.path.exists(self.LOG_PATH):
            with open(self.LOG_PATH, "w") as f:
                f.write("[]")
        self._ensure_log()

    def _ensure_log(self):
        try:
            with open(self.LOG_PATH, "r") as f:
                json.load(f)
        except (OSError, ValueError) as e:
            logger.warning("Rollback log %s is unreadable, resetting it: %s", self.LOG_PATH, e)
            with open(self.LOG_PATH, "w") as f:
                f.write("[]")

    def _snapshot_path(self, name: str) -> str:
        """The file for a snapshot name. Names are plain words: "../../x" is refused, not resolved."""
        if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name) or ".." in name:
            raise ValueError("snapshot name must be 1-100 letters, digits, '_', '-' or '.' and start with a letter or digit")
        return os.path.join(self.SNAPSHOT_DIR, f"{name}.json")

    def create_snapshot(self, name: str, state: Dict[str, Any]) -> str:
        path = self._snapshot_path(name)
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        self._append_log({"snapshot": name, "action": "CREATE"})
        return path

    def load_snapshot(self, name: str) -> Dict[str, Any]:
        path = self._snapshot_path(name)
        if not os.path.exists(path):
            raise FileNotFoundError("Snapshot not found")
        with open(path, "r") as f:
            return json.load(f)

    def rollback(self, name: str) -> Dict[str, Any]:
        data = self.load_snapshot(name)
        self._append_log({"snapshot": name, "action": "ROLLBACK"})
        return data

    def _append_log(self, entry: Dict[str, Any]):
        with open(self.LOG_PATH, "r+") as f:
            try:
                data = json.load(f)
            except ValueError as e:
                logger.warning("Rollback log %s is unreadable, restarting it: %s", self.LOG_PATH, e)
                data = []
            data.append(entry)
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)

    def get_log(self) -> List[Dict[str, Any]]:
        with open(self.LOG_PATH, "r") as f:
            return json.load(f)

# ================================================================================