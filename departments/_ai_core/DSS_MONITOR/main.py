"""DSS monitor: classifies each node as healthy, degraded or down.

down      no heartbeat yet, or the last one is older than `timeout_s`
degraded  alive, but cpu, memory or error rate is over its limit
healthy   everything else
Works on a node list passed in, or on the DSS_CLUSTER_MANAGER registry.
"""
import time

from velaris.agentkit.aicore_a_common import health, ident, invalid, number, ok
from velaris.agents.DSS_CLUSTER_MANAGER.main import DSS_CLUSTER_MANAGERAgent

NAME = "DSS_MONITOR"
LIMITS = {"cpu": 0.85, "mem": 0.90, "error_rate": 0.05}


class DSS_MONITORAgent:
    def __init__(self, name=NAME, timeout_s=30.0, limits=None):
        self.name = name
        self.timeout_s = timeout_s
        self.limits = {**LIMITS, **(limits or {})}

    def health_check(self):
        return health(self.name)

    def assess(self, nodes=None, now=None):
        """Returns per-node state with reasons, plus the healthy / degraded / down name lists."""
        if nodes is None:
            nodes = DSS_CLUSTER_MANAGERAgent().nodes()
        if not isinstance(nodes, list):
            return invalid("nodes must be a list of node objects")
        now = time.time() if now is None else now
        report, rejected = {}, []
        for node in nodes:
            name = ident(node.get("name")) if isinstance(node, dict) else None
            if name is None or not isinstance(node.get("metrics", {}), dict):
                rejected.append(node)
                continue
            beat = number(node.get("last_heartbeat"))
            metrics = node.get("metrics", {})
            if beat is None:
                state, reasons, age = "down", ["no heartbeat received"], None
            else:
                age = round(now - beat, 3)
                over = [f"{k} {metrics[k]} over limit {limit}" for k, limit in sorted(self.limits.items())
                        if number(metrics.get(k)) is not None and metrics[k] > limit]
                if age > self.timeout_s:
                    state, reasons = "down", [f"last heartbeat {age}s ago, timeout {self.timeout_s}s"]
                elif over:
                    state, reasons = "degraded", over
                else:
                    state, reasons = "healthy", []
            report[name] = {"state": state, "reasons": reasons, "heartbeat_age_s": age, "node": node}
        by_state = {s: sorted(n for n, r in report.items() if r["state"] == s)
                    for s in ("healthy", "degraded", "down")}
        return ok(nodes=report, rejected=rejected, **by_state)
