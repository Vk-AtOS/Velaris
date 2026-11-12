"""Agent lifecycle manager: the state machine for every agent's operational state.

States: registered, active, idle, suspended, error, retired. Only the listed
transitions are accepted (a retired agent stays retired; an agent in error must
be reactivated, suspended or retired), and each accepted change is kept with
its time and reason. AGENT_LIFECYCLE is a thin front for this class.
State: <VELARIS_DATA>/agents/AGENT_LIFECYCLE_MANAGER/state.json.
"""
import time
from typing import Any, Dict

from velaris.agentkit.checks import ident
from velaris.agentkit.results import health
from velaris.agentkit.state import JsonState

NAME = "AGENT_LIFECYCLE_MANAGER"
TRANSITIONS = {
    "unknown": {"registered", "active", "idle"},
    "registered": {"active", "retired"},
    "active": {"idle", "suspended", "error", "retired"},
    "idle": {"active", "suspended", "error", "retired"},
    "suspended": {"active", "retired"},
    "error": {"active", "suspended", "retired"},
    "retired": set(),
}


class LifecycleManager:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.version = self.config.get("version", "1.0.0")
        self._state = JsonState(NAME, "state.json", {"agents": {}})

    def health_check(self):
        return health(NAME, version=self.version)

    @property
    def states(self) -> Dict[str, Dict[str, Any]]:
        """{agent: {"state": ...}} for every agent seen (read-only view)."""
        return {a: {"state": rec["state"]} for a, rec in self._state.load()["agents"].items()}

    def set_state(self, agent_name: str, state: str, reason: str = "", now: float = None):
        """Returns ok=True with the new state, or ok=False with the unchanged state and why."""
        if ident(agent_name) is None or not isinstance(state, str) or state not in TRANSITIONS or state == "unknown":
            return {"ok": False, "status": "invalid_input", "agent": agent_name, "state": "unknown",
                    "reason": f"need an agent name and a state in {sorted(set(TRANSITIONS) - {'unknown'})}"}
        now = time.time() if now is None else now

        def change(data):
            rec = data["agents"].get(agent_name, {"state": "unknown", "history": []})
            current = rec["state"]
            if state == current:
                return {"ok": True, "status": "ok", "agent": agent_name, "state": current, "changed": False}
            if state not in TRANSITIONS[current]:
                return {"ok": False, "status": "refused", "agent": agent_name, "state": current,
                        "reason": f"{current} -> {state} is not allowed; allowed: {sorted(TRANSITIONS[current])}"}
            rec["state"], rec["since"] = state, now
            rec["history"] = (rec["history"] + [{"from": current, "to": state, "at": now, "reason": str(reason)}])[-100:]
            data["agents"][agent_name] = rec
            return {"ok": True, "status": "ok", "agent": agent_name, "state": state, "changed": True,
                    "previous": current}
        return self._state.update(change)

    def get_state(self, agent_name: str):
        rec = self._state.load()["agents"].get(agent_name) if isinstance(agent_name, str) else None
        return {"state": rec["state"], "since": rec["since"]} if rec else {"state": "unknown"}

    def history(self, agent_name: str):
        rec = self._state.load()["agents"].get(agent_name) if isinstance(agent_name, str) else None
        return rec["history"] if rec else []

    def list_agents(self, state: str = None):
        """Agent names, optionally only those in one state."""
        return sorted(a for a, rec in self._state.load()["agents"].items() if state is None or rec["state"] == state)
