# ================================================================================

import os
from typing import List, Dict, Any

from velaris.agentkit.state import JsonState
from velaris.intel.paths import agent_dir

MAX_LOG = 1000

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
        self.LOG_PATH = os.path.join(self.AGENT_DIR, "dryrun.json")
        self._log = JsonState("DRY_RUN_SIMULATION", path=self.LOG_PATH)   # owner-only, atomic, locked across workers
        self.dry_run = dry_run
        self.actions_logged: List[Dict[str, Any]] = []
        self.actions_executed: List[Dict[str, Any]] = []

    def log_action(self, action_name: str, payload: Dict[str, Any]):
        entry = {"action": action_name, "payload": payload}
        self.actions_logged.append(entry)
        self._append_log({"simulated": entry})
        return entry

    def _append_log(self, record: Dict[str, Any]):
        self._log.update(lambda d: d.__setitem__("log", (d.get("log", []) + [record])[-MAX_LOG:]))

    def execute_action(self, action_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        If dry_run is True: only simulate (log and return simulated result)
        If dry_run is False: mark as executed (but for safety this method does NOT perform external side-effects)
        and returns a result dict indicating execution.
        """
        if self.dry_run:
            self.log_action(action_name, payload)       # only a dry run is logged as "simulated"
            result = {"status": "SIMULATED", "action": action_name, "payload": payload}
            return result
        else:
            # Simulated "execution" without real side-effects: record executed list
            exec_entry = {"action": action_name, "payload": payload, "status": "EXECUTED"}
            self.actions_executed.append(exec_entry)
            self._append_log({"executed": exec_entry})
            return exec_entry

    def toggle_dry_run(self, val: bool):
        self.dry_run = bool(val)

    def read_log(self):
        return list(self._log.load().get("log", []))


# ================================================================================