"""VCAS_AUTOPILOT: runs a task through a registered handler, once, and only with an approval.

register(action, handler) adds a Python callable taking the task's params and
returning a JSON-able result. execute(task, approval) runs it only when
`approval` carries the trace hash of either PRIME's "allow" decision for this
task id, principal, action, resource, amount and currency, or VCAS_CORE's
record of a person approving this task id. The hash is looked up in the
trace, so an approval cannot be made up by the caller, and each hash is
spent once (kept in the same state file), so it cannot be replayed. A task id that
already ran is never run again: the stored result is returned instead
(state under this agent's state directory, survives restart). Handler errors
are caught and recorded as a failed run. Every run is written to the trace.
ponytail: handlers live in the process; after a restart callers register them
again. A task that crashed the process mid-run is marked "started" and needs a
person to decide whether to run it again.
"""
import logging
import time
from typing import Any, Callable, Dict, Optional

from velaris.agentkit.aicore_b_common import JsonState, fail, health, ident, invalid, jsonable
from velaris.agents.VCAS_SUPERVISOR.main import task_error
from velaris.intel import trace

logger = logging.getLogger("VCAS_AUTOPILOT")
NAME = "VCAS_AUTOPILOT"


def _proven(task: Dict[str, Any], approval: Any) -> bool:
    """Is `approval` backed by a trace entry that approves this task?"""
    wanted = approval.get("trace_hash") if isinstance(approval, dict) else None
    if not isinstance(wanted, str):
        return False
    # ponytail: linear scan of the trace; index decisions by hash if the trace grows large
    entry = next((e for e in trace.entries() if e.get("hash") == wanted), None)
    if entry is None:
        return False
    p = entry["payload"]
    ctx = task.get("context") or {}
    if entry["actor"] == "PRIME" and entry["action"] == "prime.decision":
        return (p.get("decision") == "allow" and p.get("task_id") == str(task["id"])
                and p.get("principal") == task["principal"] and p.get("action") == task["action"]
                and p.get("resource") == task.get("resource")
                and p.get("amount") == ctx.get("amount") and p.get("currency") == ctx.get("currency"))
    if entry["actor"] == "VCAS_CORE" and entry["action"] == "decision":
        return p.get("approved") is True and p.get("task_id") == str(task["id"])
    return False


class VCASAutopilotAgent:
    def __init__(self):
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._runs = JsonState(NAME, "runs.json", {"runs": {}})

    def health_check(self):
        return health(NAME, handlers=sorted(self._handlers))

    def register(self, action: str, handler: Callable[[Dict[str, Any]], Any]) -> Dict[str, Any]:
        if ident(action) is None or not callable(handler):
            return invalid("register needs an action name and a callable")
        self._handlers[action] = handler
        return {"status": "ok", "action": action}

    def handlers(self):
        return sorted(self._handlers)

    def run_of(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._runs.load().get("runs", {}).get(str(task_id))

    def execute(self, task: Any, approval: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        base = {"executed": False, "task": task}
        err = task_error(task)
        if err:
            return {**base, **invalid(err)}
        task_id = str(task["id"])
        if not _proven(task, approval):
            return {**base, **fail("not_approved", "execute needs a recorded approval of this task (trace_hash)")}
        handler = self._handlers.get(task["action"])
        if handler is None:
            return {**base, **fail("no_handler", f"no handler is registered for '{task['action']}'")}
        previous = self.run_of(task_id)
        if previous is not None:
            return {**base, "status": "already_run", "run": previous,
                    "reason": "this task id already ran; its recorded result is returned"}
        def claim(state):      # check and spend in one locked write, so two callers cannot both run it
            if task_id in state.setdefault("runs", {}):
                return "already_run"
            if approval["trace_hash"] in state.setdefault("spent", []):
                return "spent"
            state["runs"][task_id] = {"state": "started", "action": task["action"], "started": time.time()}
            state["spent"].append(approval["trace_hash"])
            return None
        refused = self._runs.update(claim)
        if refused == "already_run":
            return {**base, "status": "already_run", "run": self.run_of(task_id),
                    "reason": "this task id already ran; its recorded result is returned"}
        if refused == "spent":
            return {**base, **fail("not_approved", "this approval was already used")}
        try:
            output = handler(dict(task.get("params") or {}))
            run = {"state": "done", "result": output if jsonable(output) else repr(output)}
        except Exception as e:      # a handler is outside code: record the failure, never crash the caller
            logger.warning("VCAS_AUTOPILOT: handler for %s failed: %s", task["action"], e)
            run = {"state": "failed", "error": f"{type(e).__name__}: {e}"[:300]}
        run.update(action=task["action"], finished=time.time())
        self._runs.update(lambda s: s["runs"].__setitem__(task_id, run))
        trace.append(NAME, "run", {"task_id": task_id, "action": task["action"], "state": run["state"]})
        return {**base, "executed": run["state"] == "done", "status": "ok" if run["state"] == "done" else "failed",
                "run": run}
