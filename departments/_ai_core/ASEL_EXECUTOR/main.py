"""ASEL executor: runs the steps of a plan in dependency order through caller-supplied handlers.

`handlers` maps a handler name to a Python callable taking the step. A step
runs only when every step it depends on is done. It is blocked (and everything
after it skipped) when it has no handler or needs an approval that was not
given; a handler that raises marks the step failed, and the run carries on with
whatever does not depend on it. The executor never invents a handler and never
retries. Each run is journalled.
State (last 50 runs): <VELARIS_DATA>/agents/ASEL_EXECUTOR/state.json.
"""
import logging
import time
import uuid

from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.agentkit.graph import order as dependency_order

NAME = "ASEL_EXECUTOR"
logger = logging.getLogger(NAME)


class ASEL_EXECUTORAgent:
    def __init__(self, name=NAME):
        self.name = name
        self._state = JsonState(NAME, "state.json", {"runs": []})

    def health_check(self):
        return health(self.name)

    def execute(self, plan, handlers, approved=()):
        """plan: list (or planner/router result) of {"id", "depends_on"?, "handler"|"action", "requires_approval"?}."""
        steps = plan.get("steps") if isinstance(plan, dict) else plan
        if not isinstance(steps, list) or not all(isinstance(s, dict) and ident(s.get("id")) for s in steps):
            return invalid("plan must be a list of steps with an 'id'")
        if not isinstance(handlers, dict) or not all(callable(h) for h in handlers.values()):
            return invalid("handlers must map names to callables")
        if not isinstance(approved, (list, tuple, set, frozenset)):
            return invalid("approved must be a list of step ids")
        by_id = {s["id"]: s for s in steps}
        deps = {sid: s.get("depends_on") or [] for sid, s in by_id.items()}
        if len(by_id) != len(steps) or not all(isinstance(d, list) for d in deps.values()):
            return invalid("step ids must be unique and depends_on a list")
        graph = dependency_order(deps)
        if graph["missing"] or graph["unordered"]:
            return fail("invalid_plan", "unknown or circular dependencies",
                        missing=graph["missing"], cycle=graph["unordered"])
        outcome = {}
        for sid in graph["order"]:
            step = by_id[sid]
            handler_name = step.get("handler") or step.get("action")
            waiting = [d for d in deps[sid] if outcome[d]["state"] != "done"]
            if waiting:
                outcome[sid] = {"state": "skipped", "reason": f"depends on {waiting}, not done"}
            elif step.get("requires_approval") and sid not in approved:
                outcome[sid] = {"state": "blocked", "reason": "needs approval"}
            elif handler_name not in handlers:
                outcome[sid] = {"state": "blocked", "reason": f"no handler named {handler_name!r}"}
            else:
                try:
                    outcome[sid] = {"state": "done", "handler": handler_name, "result": handlers[handler_name](step)}
                except Exception as e:      # a handler is outside code: any failure is a step failure, not a crash
                    logger.warning("step %s failed in handler %s: %s", sid, handler_name, e)
                    outcome[sid] = {"state": "failed", "handler": handler_name, "error": f"{type(e).__name__}: {e}"}
        counts = {state: sum(1 for o in outcome.values() if o["state"] == state)
                  for state in ("done", "failed", "blocked", "skipped")}
        run = {"run_id": uuid.uuid4().hex, "at": time.time(), "steps": outcome, "counts": counts,
               "order": graph["order"]}
        self._state.update(lambda data: data.update(runs=(data["runs"] + [run])[-50:]))
        if counts["done"] == len(steps):
            return ok(**run)
        return fail("partial", f"{len(steps) - counts['done']} of {len(steps)} step(s) did not complete", **run)

    def get_run(self, run_id=None):
        """A journalled run by id, or the most recent one."""
        runs = self._state.load()["runs"]
        match = [r for r in runs if run_id is None or r["run_id"] == run_id]
        return ok(run=match[-1]) if match else fail("not_found", f"no run {run_id!r}")
