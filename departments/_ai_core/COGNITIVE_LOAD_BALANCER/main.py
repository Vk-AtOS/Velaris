# ================================================================================

import logging
from typing import Dict, Any, List
from velaris.agents.AGENT_LIFECYCLE_MANAGER.main import LifecycleManager

logger = logging.getLogger("COGNITIVE_LOAD_BALANCER")

class LoadBalancer:
    def __init__(self, config: Dict[str, Any] = None):
        self.lm = LifecycleManager()
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        return {"agent": "COGNITIVE_LOAD_BALANCER", "status": "ok", "version": self.version}

    def choose(self, candidates: List[str]) -> str:
        # simple policy: choose first active or first candidate
        for c in candidates:
            st = self.lm.get_state(c)
            if st.get("state") == "active":
                return c
        return candidates[0] if candidates else ""

# ================================================================================