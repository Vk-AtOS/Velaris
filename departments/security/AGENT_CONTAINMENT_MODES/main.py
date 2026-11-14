# ================================================================================

from typing import Dict, Any

from velaris.core.access import SECURITY_ADMINS, check_caller


class AgentContainmentModes:
    """
    Velaris Agent Containment Modes
    - Supports SANDBOX, ISOLATION, and FULL_LOCK modes
    - Controls operational constraints on agents
    - Tracks status per agent
    """

    VALID_MODES = ["SANDBOX", "ISOLATION", "FULL_LOCK"]

    def __init__(self):
        self.modes: Dict[str, str] = {}
        self.metadata: Dict[str, Dict[str, Any]] = {}

    def set_mode(self, agent: str, mode: str) -> bool:
        if mode not in self.VALID_MODES or not isinstance(agent, str) or not agent:
            return False
        _, refused = check_caller("AGENT_CONTAINMENT_MODES", "set_mode", {"agent": agent[:128], "mode": mode},
                                  roles=SECURITY_ADMINS)
        if refused:
            return False
        self.modes[agent] = mode
        return True

    def get_mode(self, agent: str) -> str:
        return self.modes.get(agent, "UNSET")

    def set_metadata(self, agent: str, info: Dict[str, Any]) -> bool:
        _, refused = check_caller("AGENT_CONTAINMENT_MODES", "set_metadata", {"agent": str(agent)[:128]},
                                  roles=SECURITY_ADMINS)
        if refused:
            return False
        self.metadata[agent] = info
        return True

    def get_metadata(self, agent: str) -> Dict[str, Any]:
        return self.metadata.get(agent, {})

    def allowed_actions(self, agent: str):
        mode = self.get_mode(agent)
        if mode == "SANDBOX":
            return ["read", "compute"]
        elif mode == "ISOLATION":
            return ["compute"]
        elif mode == "FULL_LOCK":
            return []
        return []

# ================================================================================