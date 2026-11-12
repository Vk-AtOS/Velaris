"""DSS failover: keeps one primary node and promotes a standby when it goes down.

The primary is replaced only when DSS_MONITOR reports it down (a degraded
primary stays, to avoid flapping). The successor is chosen deterministically:
healthy before degraded, then highest priority, then lowest name. Every change
increments a term number so stale primaries can be recognised.
State: <VELARIS_DATA>/agents/DSS_FAILOVER/state.json.
"""
import time

from velaris.agentkit.checks import number
from velaris.agentkit.results import fail, health, ok
from velaris.agentkit.state import JsonState
from velaris.agents.DSS_MONITOR.main import DSS_MONITORAgent

NAME = "DSS_FAILOVER"


class DSS_FAILOVERAgent:
    def __init__(self, name=NAME):
        self.name = name
        self._state = JsonState(NAME, "state.json", {"primary": None, "term": 0, "history": []})

    def health_check(self):
        return health(self.name)

    def status(self):
        data = self._state.load()
        return ok(primary=data["primary"], term=data["term"], history=data["history"])

    def evaluate(self, nodes=None, now=None):
        """Check the primary against current health and promote a standby if it is down."""
        report = DSS_MONITORAgent().assess(nodes, now)
        if report["status"] != "ok":
            return report
        now = time.time() if now is None else now

        def change(data):
            current = data["primary"]
            if current in report["healthy"] or current in report["degraded"]:
                return ok(primary=current, term=data["term"], changed=False, previous=current)
            successor = None
            for tier in ("healthy", "degraded"):
                ranked = sorted(report[tier], key=lambda n: (
                    -(number(report["nodes"][n]["node"].get("priority", 0)) or 0.0), n))
                if ranked:
                    successor = ranked[0]
                    break
            why = "no primary yet" if current is None else f"primary {current} is down or gone"
            data["primary"] = successor
            data["term"] += 1
            data["history"] = (data["history"] + [{"term": data["term"], "from": current, "to": successor,
                                                   "at": now, "why": why}])[-100:]
            if successor is None:
                return fail("no_candidate", f"{why} and no node is alive to take over",
                            primary=None, term=data["term"], changed=current is not None, previous=current)
            return ok(primary=successor, term=data["term"], changed=True, previous=current, why=why)
        return self._state.update(change)
