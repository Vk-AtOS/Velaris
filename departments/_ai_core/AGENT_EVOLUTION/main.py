import logging
from typing import Dict, Any

logger = logging.getLogger("AGENT_EVOLUTION")

class EvolutionEngine:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.history = {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        return {"agent": "AGENT_EVOLUTION", "status": "ok", "version": self.version}

    def record(self, agent_name: str, metric: Dict[str, float]):
        self.history.setdefault(agent_name, []).append(metric)
        logger.debug("Recorded metric for %s: %s", agent_name, metric)
        return {"ok": True}

    def propose(self, agent_name: str):
        # trivial heuristic: if agent had >5 records, propose a noop or minor param
        rec = self.history.get(agent_name, [])
        if len(rec) > 5:
            return {"agent": agent_name, "proposal": "tune-params"}
        return {"agent": agent_name, "proposal": "none"}
