"""ASEL planner: schedules a set of dependent tasks (critical path method).

Each task is {"id", "duration"?, "depends_on"?, ...}. The planner orders them,
computes earliest start and finish, slack and the critical path, and returns
the total duration. Unknown or circular dependencies make the plan invalid.
Resources are not modelled: tasks with no dependency between them are assumed
to run in parallel.
"""
from velaris.agentkit.aicore_a_common import fail, health, ident, invalid, number, ok, topo_levels

NAME = "ASEL_PLANNER"


class ASEL_PLANNERAgent:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def plan(self, tasks):
        if not isinstance(tasks, list) or not tasks:
            return invalid("tasks must be a non-empty list")
        by_id = {}
        for task in tasks:
            tid = ident(task.get("id")) if isinstance(task, dict) else None
            duration = number(task.get("duration", 1)) if tid else None
            deps = task.get("depends_on", []) if tid else None
            if tid is None or tid in by_id or duration is None or duration < 0:
                return invalid(f"task {task!r} needs a unique id and a non-negative duration")
            if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
                return invalid(f"task {tid}: depends_on must be a list of task ids")
            by_id[tid] = {**task, "id": tid, "duration": duration, "depends_on": list(deps)}
        graph = topo_levels({tid: t["depends_on"] for tid, t in by_id.items()})
        if graph["missing"] or graph["cycle"]:
            return fail("invalid_plan", "unknown or circular dependencies",
                        missing=graph["missing"], cycle=graph["cycle"])
        for tid in graph["order"]:
            task = by_id[tid]
            task["start"] = max((by_id[d]["finish"] for d in task["depends_on"]), default=0.0)
            task["finish"] = task["start"] + task["duration"]
        total = max(t["finish"] for t in by_id.values())
        for tid in reversed(graph["order"]):
            followers = [t for t in by_id.values() if tid in t["depends_on"]]
            latest_finish = min((t["finish"] + t["slack"] - t["duration"] for t in followers), default=total)
            by_id[tid]["slack"] = round(latest_finish - by_id[tid]["finish"], 6)
        critical = [tid for tid in graph["order"] if by_id[tid]["slack"] == 0]
        return ok(steps=[by_id[tid] for tid in graph["order"]], levels=graph["levels"],
                  critical_path=critical, total_duration=total)
