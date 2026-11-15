# ================================================================================

"""Cognitive load balancer: picks which candidate agent should take a task, by lifecycle state.

LoadBalancer.choose(candidates) returns the first candidate whose LifecycleManager state is
"active", else the first candidate, else "" for an empty list. This is a plain first-match
rule, not a load measurement. health_check() reports status and version (config["version"],
default 0.1.0). Keeps no state of its own; state comes from the AGENT_LIFECYCLE_MANAGER agent.
Failure behaviour: no validation; an error from the lifecycle lookup propagates.
"""
import logging
from typing import Dict, Any, List
from velaris.agents.AGENT_LIFECYCLE_MANAGER.main import LifecycleManager

logger = logging.getLogger("COGNITIVE_LOAD_BALANCER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - COGNITIVE_LOAD_BALANCER - %(levelname)s - %(message)s"))
logger.addHandler(handler)

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