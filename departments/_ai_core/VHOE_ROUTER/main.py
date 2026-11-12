"""VHOE_ROUTER: assigns one piece of work to the person or agent best placed to take it.

VHOE is read here as "human-and-agent operations": a pool of workers (people
or agents) with skills and limited capacity, and a queue of work items.

route(item, workers) picks, among the workers who have the item's skill and
enough free capacity for its effort, the one with the lowest utilisation
(load / capacity); ties go to the worker id that sorts first. When nobody
qualifies it says whether the skill or the capacity was missing.

item:   {"id", "skill", "effort": hours (default 1)}
worker: {"id", "skills": [...], "capacity": hours, "load": hours (default 0)}
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import ident, number
from velaris.agentkit.results import fail, health, invalid

NAME = "VHOE_ROUTER"


def item_error(item: Any) -> Optional[str]:
    if not isinstance(item, dict) or ident(str(item.get("id", ""))) is None or ident(item.get("skill")) is None:
        return "an item needs 'id' and 'skill'"
    effort = number(item.get("effort", 1))
    if effort is None or effort <= 0:
        return f"item {item['id']}: effort must be a positive number"
    return None


def worker_error(worker: Any) -> Optional[str]:
    if not isinstance(worker, dict) or ident(str(worker.get("id", ""))) is None:
        return "a worker needs an 'id'"
    skills = worker.get("skills")
    if not isinstance(skills, list) or any(ident(s) is None for s in skills):
        return f"worker {worker['id']}: skills must be a list of names"
    capacity, load = number(worker.get("capacity")), number(worker.get("load", 0))
    if capacity is None or capacity <= 0 or load is None or load < 0:
        return f"worker {worker['id']}: capacity must be positive and load not negative"
    return None


class VHOE_ROUTERAgent:
    def health_check(self):
        return health(NAME)

    def route(self, item: Dict[str, Any], workers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Returns the chosen worker id, or status "unassigned" with the reason."""
        if not isinstance(workers, list) or not workers:
            return invalid("workers must be a non-empty list", worker=None)
        err = item_error(item) or next((e for e in map(worker_error, workers) if e), None)
        if err:
            return invalid(err, worker=None)
        effort = float(item.get("effort", 1))
        skilled = [w for w in workers if item["skill"] in w["skills"]]
        if not skilled:
            return fail("unassigned", f"nobody has the skill {item['skill']!r}", worker=None, cause="no_skill")
        free = [w for w in skilled if w.get("load", 0) + effort <= w["capacity"]]
        if not free:
            return fail("unassigned", f"everyone with {item['skill']!r} is at capacity", worker=None,
                        cause="no_capacity")
        best = min(free, key=lambda w: (w.get("load", 0) / w["capacity"], str(w["id"])))
        return {"status": "ok", "worker": best["id"], "item": item["id"], "effort": effort,
                "utilisation_after": round((best.get("load", 0) + effort) / best["capacity"], 3),
                "candidates": len(free)}
