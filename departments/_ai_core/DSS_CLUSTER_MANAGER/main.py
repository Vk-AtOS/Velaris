"""DSS cluster manager: the registry of worker nodes for the DSS family.

Keeps which nodes exist, their weight, zone and failover priority, and the last
heartbeat and metrics each one reported. DSS_MONITOR, DSS_LOAD_BALANCER and
DSS_FAILOVER read this registry when they are not handed a node list.
State: <VELARIS_DATA>/agents/DSS_CLUSTER_MANAGER/state.json.
"""
import time

from velaris.agentkit.aicore_a_common import JsonState, fail, health, ident, invalid, number, ok
from velaris.intel.paths import agent_dir

NAME = "DSS_CLUSTER_MANAGER"
METRICS = ("cpu", "mem", "error_rate", "active", "capacity")


class DSS_CLUSTER_MANAGERAgent:
    def __init__(self, name=NAME):
        self.name = name
        self._state = JsonState(lambda: agent_dir(NAME) / "state.json", {"nodes": {}})

    def health_check(self):
        return health(self.name)

    def register_node(self, node, weight=1.0, zone="default", priority=0, now=None):
        """Add a node or update its weight, zone and priority. Heartbeat data is kept."""
        node, zone = ident(node), ident(zone)
        weight, priority = number(weight), number(priority)
        if node is None or zone is None:
            return invalid("node and zone must be non-empty strings")
        if weight is None or weight <= 0 or priority is None:
            return invalid("weight must be a positive number and priority a number")
        now = time.time() if now is None else now

        def change(data):
            rec = data["nodes"].setdefault(node, {"name": node, "registered_at": now,
                                                  "last_heartbeat": None, "metrics": {}})
            rec.update(weight=weight, zone=zone, priority=priority)
            return dict(rec)
        return ok(node=self._state.update(change))

    def deregister_node(self, node):
        def change(data):
            return data["nodes"].pop(node, None) if isinstance(node, str) else None
        removed = self._state.update(change)
        return ok(removed=node) if removed else fail("not_found", f"no node named {node!r}")

    def heartbeat(self, node, metrics=None, now=None):
        """Record that a registered node is alive, with optional numeric metrics."""
        if metrics is not None and not isinstance(metrics, dict):
            return invalid("metrics must be an object")
        clean = {}
        for key, value in (metrics or {}).items():
            if key not in METRICS or number(value) is None or value < 0:
                return invalid(f"metric {key!r} must be one of {METRICS} with a non-negative number")
            clean[key] = float(value)
        now = time.time() if now is None else now

        def change(data):
            rec = data["nodes"].get(node) if isinstance(node, str) else None
            if rec is None:
                return None
            rec["last_heartbeat"] = now
            rec["metrics"].update(clean)
            return dict(rec)
        rec = self._state.update(change)
        # An unregistered node cannot join by heartbeating: registration is the explicit step.
        return ok(node=rec) if rec else fail("not_found", f"node {node!r} is not registered")

    def nodes(self):
        """All registered nodes, sorted by name."""
        return [rec for _, rec in sorted(self._state.load()["nodes"].items())]
