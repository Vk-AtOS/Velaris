"""Agent evolution: records per-agent metrics and proposes a tuning action when a cost metric is getting worse.
EvolutionEngine.record(agent_name, metric) keeps a dict of numbers for the agent (at most 200 per agent, 1,000 agents; a
bad name or a metric that is not a dict of finite numbers returns {"ok": False, "reason": ...} and records nothing).
propose(agent_name) returns {"agent", "proposal"}: "tune-params" when more than 5 metrics are recorded and the mean of
a cost metric ("loss", "error", "errors", "latency", "cost") over the newer half is higher than over the older half,
otherwise "none". The metric values ARE read: a steady or improving agent is never proposed for tuning. This is still
a heuristic; it proposes, it changes nothing.
health_check() returns {"agent", "status": "ok", "version"}.
State: in-memory dict only, nothing persisted. A non-dict config is treated as empty.
"""
import logging
import math
from typing import Dict, Any

logger = logging.getLogger("AGENT_EVOLUTION")
COST_METRICS = ("loss", "error", "errors", "latency", "cost")
MAX_PER_AGENT = 200
MAX_AGENTS = 1000


class EvolutionEngine:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config if isinstance(config, dict) else {}
        self.history = {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        return {"agent": "AGENT_EVOLUTION", "status": "ok", "version": self.version}

    def record(self, agent_name: str, metric: Dict[str, float]):
        if not isinstance(agent_name, str) or not agent_name.strip() or len(agent_name) > 120:
            return {"ok": False, "reason": "agent_name must be non-empty text"}
        if not isinstance(metric, dict) or not metric or not all(
                isinstance(k, str) and isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for k, v in metric.items()):
            return {"ok": False, "reason": "metric must be a non-empty dict of finite numbers"}
        if agent_name not in self.history and len(self.history) >= MAX_AGENTS:
            return {"ok": False, "reason": "too many agents are tracked"}
        rec = self.history.setdefault(agent_name, [])
        rec.append(dict(metric))
        del rec[:-MAX_PER_AGENT]
        logger.debug("Recorded metric for %s: %s", agent_name, metric)
        return {"ok": True}

    def propose(self, agent_name: str):
        rec = self.history.get(agent_name, []) if isinstance(agent_name, str) else []
        if len(rec) > 5:
            half = len(rec) // 2
            for key in COST_METRICS:
                old = [m[key] for m in rec[:half] if key in m]
                new = [m[key] for m in rec[-half:] if key in m]
                if old and new and sum(new) / len(new) > sum(old) / len(old):
                    return {"agent": agent_name, "proposal": "tune-params"}
        return {"agent": agent_name, "proposal": "none"}
