"""VHOE_CORE: one planning pass over the work queue.

plan(items, workers, history) assigns the queue with VHOE_OPTIMIZER and, when
past completion records are given, adds VHOE_ANALYTICS' picture of how work
has been going. It then flags what a manager should look at: unassigned work,
workers above 90% utilisation, and a late rate above 20%.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit.aicore_b_common import health
from velaris.agents.VHOE_ANALYTICS.main import VHOE_ANALYTICSAgent
from velaris.agents.VHOE_OPTIMIZER.main import VHOE_OPTIMIZERAgent

NAME = "VHOE_CORE"
HIGH_UTILISATION, HIGH_LATE_RATE = 0.9, 0.2


class VHOE_COREAgent:
    def __init__(self):
        self.optimizer = VHOE_OPTIMIZERAgent()
        self.analytics = VHOE_ANALYTICSAgent()

    def health_check(self):
        return health(NAME)

    def plan(self, items: List[Dict[str, Any]], workers: List[Dict[str, Any]],
             history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        result = self.optimizer.optimize(items, workers)
        if result["status"] != "ok":
            return {**result, "flags": []}
        flags = []
        if result["unassigned"]:
            flags.append(f"{len(result['unassigned'])} item(s) could not be assigned")
        flags += [f"{w} is at {u:.0%} of capacity" for w, u in sorted(result["utilisation"].items())
                  if u > HIGH_UTILISATION]
        if history is not None:
            past = self.analytics.analyse(history)
            result["history"] = past
            if past.get("late_rate") is not None and past["late_rate"] > HIGH_LATE_RATE:
                flags.append(f"{past['late_rate']:.0%} of past work with a due time finished late")
        return {**result, "flags": flags}
