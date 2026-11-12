"""VHOE_OPTIMIZER: assigns a whole queue of work to a pool of workers.

Items are taken most important first (priority 1 is highest, then the earliest
"due", then id) and each is placed with VHOE_ROUTER against the loads built up
so far, so the important work gets capacity before the rest. The result lists
every assignment, what could not be assigned and why, and each worker's
utilisation afterwards.
ponytail: greedy, one pass. It respects priority and capacity but does not
search for the best overall packing; use an assignment solver if leftover
capacity is being wasted.
"""
from typing import Any, Dict, List

from velaris.agentkit.checks import number
from velaris.agentkit.results import health, invalid
from velaris.agents.VHOE_ROUTER.main import VHOE_ROUTERAgent, item_error, worker_error

NAME = "VHOE_OPTIMIZER"
MAX_ITEMS = 5000


class VHOE_OPTIMIZERAgent:
    def __init__(self):
        self.router = VHOE_ROUTERAgent()

    def health_check(self):
        return health(NAME)

    def optimize(self, items: List[Dict[str, Any]], workers: List[Dict[str, Any]]) -> Dict[str, Any]:
        empty = {"assignments": [], "unassigned": []}
        if not isinstance(items, list) or not isinstance(workers, list) or not workers or len(items) > MAX_ITEMS:
            return invalid(f"items (at most {MAX_ITEMS}) and workers must be lists; workers not empty", **empty)
        err = next((e for e in [*map(item_error, items), *map(worker_error, workers)] if e), None)
        if err:
            return invalid(err, **empty)
        if any(number(i.get("priority", 3)) is None or ("due" in i and number(i["due"]) is None) for i in items):
            return invalid("priority and due must be numbers when given", **empty)
        if len({str(w["id"]) for w in workers}) != len(workers) or len({str(i["id"]) for i in items}) != len(items):
            return invalid("item ids and worker ids must each be unique", **empty)
        pool = [{**w, "load": float(w.get("load", 0))} for w in workers]      # working copy; inputs untouched
        by_id = {w["id"]: w for w in pool}
        queue = sorted(items, key=lambda i: (i.get("priority", 3), i.get("due", float("inf")), str(i["id"])))
        assignments, unassigned = [], []
        for item in queue:
            placed = self.router.route(item, pool)
            if placed["status"] == "ok":
                by_id[placed["worker"]]["load"] += placed["effort"]
                assignments.append({"item": item["id"], "worker": placed["worker"], "effort": placed["effort"]})
            else:
                unassigned.append({"item": item["id"], "cause": placed.get("cause"), "reason": placed["reason"]})
        return {"status": "ok", "assignments": assignments, "unassigned": unassigned,
                "utilisation": {w["id"]: round(w["load"] / w["capacity"], 3) for w in pool},
                "method": "greedy by priority, due date, then least-utilised qualified worker"}
