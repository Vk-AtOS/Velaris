"""CLBPP distributor: assigns a batch of tasks to workers without overfilling anyone.

Tasks are placed largest first; each goes to the worker that has the skill, has
room, and would end up least utilised (load / capacity). A task that fits
nowhere is returned as unassigned with the reason, never squeezed in.
Deterministic greedy heuristic, not an optimal bin-packing.
"""
from velaris.agentkit.checks import ident, number
from velaris.agentkit.results import health, invalid, ok

NAME = "CLBPP_DISTRIBUTOR"


def clean_workers(workers):
    """{name: {"capacity", "load", "skills"}} or an error string."""
    if not isinstance(workers, list):
        return "workers must be a list"
    out = {}
    for w in workers:
        name = ident(w.get("name")) if isinstance(w, dict) else None
        capacity = number(w.get("capacity")) if name else None
        load = number(w.get("load", 0)) if name else None
        skills = w.get("skills") if name else None
        if name is None or capacity is None or capacity <= 0 or load is None or load < 0 or name in out:
            return f"worker {w!r} needs a unique name, a positive capacity and a non-negative load"
        if skills is not None and not isinstance(skills, list):
            return f"worker {name}: skills must be a list"
        out[name] = {"capacity": capacity, "load": load, "skills": skills}
    return out


class CLBPP_DISTRIBUTORAgent:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def distribute(self, tasks, workers):
        """tasks: [{"id", "effort", "skill"?}]; workers: [{"name", "capacity", "load"?, "skills"?}]."""
        pool = clean_workers(workers)
        if isinstance(pool, str):
            return invalid(pool)
        if not isinstance(tasks, list):
            return invalid("tasks must be a list")
        seen = set()
        for t in tasks:
            tid = ident(t.get("id")) if isinstance(t, dict) else None
            effort = number(t.get("effort")) if tid else None
            if tid is None or tid in seen or effort is None or effort <= 0:
                return invalid(f"task {t!r} needs a unique id and a positive effort")
            seen.add(tid)
        assignments, unassigned = {}, []
        for t in sorted(tasks, key=lambda t: (-t["effort"], t["id"])):
            skill = t.get("skill")
            skilled = [n for n, w in pool.items() if skill is None or (w["skills"] is not None and skill in w["skills"])]
            fits = [n for n in skilled if pool[n]["load"] + t["effort"] <= pool[n]["capacity"]]
            if not fits:
                reason = f"no worker has skill {skill!r}" if not skilled else "no skilled worker has enough spare capacity"
                unassigned.append({"id": t["id"], "reason": reason})
                continue
            best = min(fits, key=lambda n: ((pool[n]["load"] + t["effort"]) / pool[n]["capacity"], n))
            pool[best]["load"] += t["effort"]
            assignments[t["id"]] = best
        loads = {n: {"load": w["load"], "capacity": w["capacity"], "utilisation": round(w["load"] / w["capacity"], 4)}
                 for n, w in pool.items()}
        return ok(assignments=assignments, unassigned=unassigned, loads=loads)
