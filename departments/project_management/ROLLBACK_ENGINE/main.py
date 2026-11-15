# ================================================================================

"""Rollback engine: saves named state snapshots to disk and returns them on rollback.

create_snapshot(name, state) writes <name>.json and logs CREATE (overwrites an existing
snapshot); load_snapshot(name) reads it; rollback(name) returns the snapshot state and logs
ROLLBACK, it does not apply the state anywhere; get_log() returns the history list. Names must
be 1-100 letters, digits, "_", "-" or "." starting with a letter or digit, else ValueError;
a missing snapshot raises FileNotFoundError. State: snapshots/ and rollback.log (a JSON list)
under <VELARIS_DATA>/agents/ROLLBACK_ENGINE; an unreadable log is reset with a warning.
"""
import json
import os
import re
from typing import List, Dict, Any

from velaris.agentkit.secure import safe_join
from velaris.agentkit.state import JsonState
from velaris.intel.paths import agent_dir, private_dir, read_private, write_private

MAX_LOG = 1000
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")

class RollbackEngine:
    """
    Velaris Rollback Engine
    - Stores snapshots of system state (owner-only files, written atomically)
    - Allows reverting to any previous snapshot
    - Maintains a rollback history log (bounded, locked, shared by every worker)
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("ROLLBACK_ENGINE"))
        self.SNAPSHOT_DIR = str(private_dir(os.path.join(self.AGENT_DIR, "snapshots")))
        self.LOG_PATH = os.path.join(self.AGENT_DIR, "rollback.json")
        self._log = JsonState("ROLLBACK_ENGINE", path=self.LOG_PATH)

    def _snapshot_path(self, name: str) -> str:
        """The file for a snapshot name: a plain word that resolves inside the snapshots folder (shared safe_join)."""
        if not isinstance(name, str) or not _SAFE_NAME.fullmatch(name):
            raise ValueError("snapshot name must be 1-100 letters, digits, '_', '-' or '.' and start with a letter or digit")
        return str(safe_join(self.SNAPSHOT_DIR, name, ".json"))

    def create_snapshot(self, name: str, state: Dict[str, Any]) -> str:
        path = self._snapshot_path(name)
        write_private(path, json.dumps(state, indent=2, allow_nan=False))
        self._append_log({"snapshot": name, "action": "CREATE"})
        return path

    def load_snapshot(self, name: str) -> Dict[str, Any]:
        path = self._snapshot_path(name)
        try:
            return json.loads(read_private(path))
        except FileNotFoundError:
            raise FileNotFoundError("Snapshot not found") from None

    def rollback(self, name: str) -> Dict[str, Any]:
        data = self.load_snapshot(name)
        self._append_log({"snapshot": name, "action": "ROLLBACK"})
        return data

    def _append_log(self, entry: Dict[str, Any]):
        self._log.update(lambda d: d.__setitem__("log", (d.get("log", []) + [entry])[-MAX_LOG:]))

    def get_log(self) -> List[Dict[str, Any]]:
        return list(self._log.load().get("log", []))

# ================================================================================
