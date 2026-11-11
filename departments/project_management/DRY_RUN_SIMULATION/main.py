# ================================================================================

import json
import os
from typing import List, Dict, Any

from velaris.intel.paths import agent_dir

class DryRunSimulation:
    """
    Dry-Run Simulation Mode
    - Simulate actions without side-effects
    - Maintain logs for simulated vs executed actions
    - Provide a toggle for dry-run vs live
    """

    def __init__(self, dry_run: bool = True):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("DRY_RUN_SIMULATION"))
        self.LOG_PATH = os.path.join(self.AGENT_DIR, "dryrun.log")
        self.dry_run = dry_run
        self.actions_logged: List[Dict[str, Any]] = []
        self.actions_executed: List[Dict[str, Any]] = []
        # initialize log file
        if not os.path.exists(self.LOG_PATH):
            with open(self.LOG_PATH, "w") as f:
                f.write("[]")

    def log_action(self, action_name: str, payload: Dict[str, Any]):
        entry = {"action": action_name, "payload": payload}
        self.actions_logged.append(entry)
        self._append_log(entry)
        return entry

    def _append_log(self, entry: Dict[str, Any]):
        with open(self.LOG_PATH, "r+") as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
            data.append({"simulated": entry})
            f.seek(0)
            f.truncate()
            json.dump(data, f, indent=2)

    def execute_action(self, action_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        If dry_run is True: only simulate (log and return simulated result)
        If dry_run is False: mark as executed (but for safety this method does NOT perform external side-effects)
        and returns a result dict indicating execution.
        """
        logged = self.log_action(action_name, payload)
        if self.dry_run:
            result = {"status": "SIMULATED", "action": action_name, "payload": payload}
            return result
        else:
            # Simulated "execution" without real side-effects: record executed list
            exec_entry = {"action": action_name, "payload": payload, "status": "EXECUTED"}
            self.actions_executed.append(exec_entry)
            # also append to log as executed
            with open(self.LOG_PATH, "r+") as f:
                try:
                    data = json.load(f)
                except Exception:
                    data = []
                data.append({"executed": exec_entry})
                f.seek(0)
                f.truncate()
                json.dump(data, f, indent=2)
            return exec_entry

    def toggle_dry_run(self, val: bool):
        self.dry_run = bool(val)

    def read_log(self):
        with open(self.LOG_PATH, "r") as f:
            try:
                return json.load(f)
            except Exception:
                return []


# ================================================================================