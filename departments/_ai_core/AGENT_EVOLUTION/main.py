"""Agent evolution: records per-agent metrics and proposes a tuning action from a trivial count heuristic.
EvolutionEngine.record(agent_name, metric) appends a metric dict to an in-memory list for that agent.
propose(agent_name) returns {"agent", "proposal"}: "tune-params" when more than 5 metrics are recorded
for the agent, otherwise "none". This is a stub heuristic (it never reads the metric values).
health_check() returns {"agent", "status": "ok", "version"}.
State: in-memory dict only, nothing persisted. Failure: no validation; an unknown agent gives "none",
and a non-dict config raises from config.get.
"""
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
