"""DSS load balancer: weighted least-load node selection with health checks and shedding.

A request goes to the node with the fewest active requests per unit of weight.
Down nodes are never chosen; degraded nodes only when no healthy node has room;
a node at or over its capacity is skipped. When nothing has room the request is
shed (status "shed") instead of being piled onto a full node.
"""
from velaris.agentkit.checks import number
from velaris.agentkit.results import fail, health
from velaris.agents.DSS_MONITOR.main import DSS_MONITORAgent

NAME = "DSS_LOAD_BALANCER"


class DSS_LOAD_BALANCERAgent:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    @staticmethod
    def _load(node):
        """(active per weight, has room) for one node; a node with bad numbers has no room."""
        metrics = node.get("metrics", {})
        weight = number(node.get("weight", 1.0))
        active = number(metrics.get("active", 0))
        capacity = number(metrics.get("capacity")) if "capacity" in metrics else float("inf")
        if weight is None or weight <= 0 or active is None or capacity is None:
            return None, False
        return active / weight, active < capacity

    def pick(self, nodes=None, now=None, exclude=()):
        """Choose a node for one request. Returns the choice and why the others were skipped."""
        report = DSS_MONITORAgent().assess(nodes, now)
        if report["status"] != "ok":
            return report
        skipped = {n: "down" for n in report["down"]}
        for tier in ("healthy", "degraded"):
            candidates = []
            for name in report[tier]:
                load, room = self._load(report["nodes"][name]["node"])
                if name in exclude:
                    skipped[name] = "excluded by caller"
                elif not room:
                    skipped[name] = "at capacity or invalid load figures"
                else:
                    candidates.append((load, name))
            if candidates:
                load, name = min(candidates)
                return {"status": "ok", "node": name, "tier": tier, "load_per_weight": round(load, 4),
                        "skipped": skipped}
        return fail("shed", "no node is alive with spare capacity", node=None, skipped=skipped)
