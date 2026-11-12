"""SELF_DIRECTED_TASKER: works through an ordered task list, releasing tasks as their dependencies finish.

prepare(expanded) takes RECURSIVE_GOAL_PLANNER's output and says which tasks
can start now and which are blocked by what; it stores nothing.

start(expanded) stores the plan as a queue under this agent's state directory
and returns a plan_id. next_tasks(plan_id) lists the tasks that are ready,
complete(plan_id, task_id) marks one done (only a ready task can be completed)
and returns what that released. The queue survives a restart. The agent
tracks state; it does not execute the tasks itself.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import new_id
from velaris.agentkit.results import fail, health, invalid
from velaris.agentkit.state import JsonState

NAME = "SELF_DIRECTED_TASKER"


def _tasks(expanded: Any) -> Optional[List[Dict[str, Any]]]:
    inner = expanded.get("expanded", expanded) if isinstance(expanded, dict) else None
    tasks = inner.get("tasks") if isinstance(inner, dict) else None
    if not isinstance(tasks, list) or not tasks:
        return None
    ids = [t.get("id") for t in tasks if isinstance(t, dict)]
    if len(ids) != len(tasks) or len(set(ids)) != len(ids) or any(
            not isinstance(t.get("depends_on", []), list) or set(t.get("depends_on", [])) - set(ids) for t in tasks):
        return None
    return [{"id": t["id"], "title": t.get("title", ""), "depends_on": list(t.get("depends_on", []))} for t in tasks]


def _ready(tasks: Dict[str, Dict[str, Any]]) -> List[str]:
    done = {i for i, t in tasks.items() if t["state"] == "done"}
    return sorted(i for i, t in tasks.items() if t["state"] == "pending" and set(t["depends_on"]) <= done)


class SelfDirectedTasker:
    def __init__(self, name=NAME):
        self.name = name
        self._state = JsonState(NAME, "queues.json", {"plans": {}})

    def health_check(self):
        return health(self.name)

    def prepare(self, expanded: dict) -> Dict[str, Any]:
        """Which tasks are ready and which are blocked. task_ready is True when at least one can start."""
        tasks = _tasks(expanded)
        if tasks is None:
            return {"task_ready": False, "expanded": expanded, "ready": [], "blocked": {}, "status": "invalid_input",
                    "reason": "expected a planner result with a non-empty 'tasks' list and known dependencies"}
        ready = sorted(t["id"] for t in tasks if not t["depends_on"])
        return {"task_ready": bool(ready), "expanded": expanded, "ready": ready,
                "blocked": {t["id"]: t["depends_on"] for t in tasks if t["depends_on"]},
                "total": len(tasks), "status": "ok" if ready else "deadlocked"}

    def start(self, expanded: dict) -> Dict[str, Any]:
        """Store the plan as a queue. Returns plan_id and the tasks that can start."""
        checked = self.prepare(expanded)
        if checked["status"] != "ok":
            return fail(checked["status"], checked.get("reason", "no task can start"), plan_id=None)
        plan_id = new_id("queue")
        queue = {t["id"]: {**t, "state": "pending"} for t in _tasks(expanded)}        # type: ignore[union-attr]
        self._state.update(lambda s: s.setdefault("plans", {}).__setitem__(plan_id, queue))
        return {"status": "ok", "plan_id": plan_id, "ready": checked["ready"], "total": len(queue)}

    def next_tasks(self, plan_id: str) -> Dict[str, Any]:
        queue = self._state.load().get("plans", {}).get(plan_id)
        if queue is None:
            return fail("not_found", f"no queue {plan_id!r}", ready=[])
        done = sorted(i for i, t in queue.items() if t["state"] == "done")
        return {"status": "ok", "ready": [{"id": i, "title": queue[i]["title"]} for i in _ready(queue)],
                "done": done, "remaining": len(queue) - len(done), "finished": len(done) == len(queue)}

    def complete(self, plan_id: str, task_id: str) -> Dict[str, Any]:
        """Mark a ready task done. Returns the tasks this released."""
        def change(state):
            queue = state.get("plans", {}).get(plan_id)
            if queue is None:
                return fail("not_found", f"no queue {plan_id!r}")
            if task_id not in queue:
                return invalid(f"no task {task_id!r} in this queue")
            before = _ready(queue)
            if queue[task_id]["state"] == "done":
                return fail("already_done", f"task {task_id!r} was already completed")
            if task_id not in before:
                return fail("blocked", f"task {task_id!r} is waiting for "
                                       f"{sorted(d for d in queue[task_id]['depends_on'] if queue[d]['state'] != 'done')}")
            queue[task_id]["state"] = "done"
            after = _ready(queue)
            return {"status": "ok", "completed": task_id, "released": [i for i in after if i not in before],
                    "finished": all(t["state"] == "done" for t in queue.values())}
        return self._state.update(change)
