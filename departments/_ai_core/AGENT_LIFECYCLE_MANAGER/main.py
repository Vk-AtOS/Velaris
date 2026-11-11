import logging
from typing import Dict, Any

logger = logging.getLogger("AGENT_LIFECYCLE_MANAGER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - AGENT_LIFECYCLE_MANAGER - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class LifecycleManager:
    """
    Tracks simple state for agents. States: active, idle, suspended, error.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.states = {}
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        return {"agent": "AGENT_LIFECYCLE_MANAGER", "status": "ok", "version": self.version}

    def set_state(self, agent_name: str, state: str):
        self.states[agent_name] = {"state": state}
        logger.debug("Set %s -> %s", agent_name, state)
        return {"ok": True, "agent": agent_name, "state": state}

    def get_state(self, agent_name: str):
        return self.states.get(agent_name, {"state": "unknown"})
