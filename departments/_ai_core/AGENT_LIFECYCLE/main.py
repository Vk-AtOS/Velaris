"""Agent lifecycle: message-style front for AGENT_LIFECYCLE_MANAGER.

run({"action": "set" | "get" | "history" | "list", "agent", "state", "reason"})
maps one request onto the manager, which holds the state machine and the state
file. This class adds no rules of its own.
"""
from typing import Any, Dict

from velaris.agentkit.aicore_a_common import fail, health
from velaris.agents.AGENT_LIFECYCLE_MANAGER.main import LifecycleManager

NAME = "AGENT_LIFECYCLE"


class AgentLifecycleAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", "1.0.0")
        self.manager = LifecycleManager(config)

    def health_check(self) -> Dict[str, Any]:
        return health(NAME, version=self.version)

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return fail("invalid_input", "payload must be an object with an 'action'", payload=payload)
        action, agent = payload.get("action"), payload.get("agent")
        if action == "set":
            result = self.manager.set_state(agent, payload.get("state"), payload.get("reason", ""))
        elif action == "get":
            result = {"status": "ok", "agent": agent, **self.manager.get_state(agent)}
        elif action == "history":
            result = {"status": "ok", "agent": agent, "history": self.manager.history(agent)}
        elif action == "list":
            result = {"status": "ok", "agents": self.manager.list_agents(payload.get("state"))}
        else:
            return fail("invalid_input", "action must be one of set, get, history, list", payload=payload)
        return {**result, "payload": payload}
