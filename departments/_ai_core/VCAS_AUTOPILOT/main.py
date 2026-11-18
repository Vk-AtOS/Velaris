"""VCAS_AUTOPILOT: runs a task through a registered handler, once, and only with an approval.

register(action, handler) adds a Python callable taking the task's params and
returning a JSON-able result. execute(task, approval) runs it only when
`approval` carries the trace hash of either PRIME's "allow" decision or VCAS_CORE's
record of a person approving, and that decision carries the same
aicore_b_authz.task_digest as the task given here: id, action, principal,
resource, context (amount, currency ...) and params, so nothing the handler
receives can differ from what was approved. The run is also bound to the caller
(velaris.core.access): a PRIME allow runs only for the task's principal, a
person's approval only for that person. The hash is looked up in the
trace, so an approval cannot be made up by the caller, and each hash is
spent once (kept in the same state file), so it cannot be replayed. A task id that
already ran is never run again: the stored result is returned instead
(state under this agent's state directory, survives restart). Handler errors
are caught and recorded as a failed run. Every run is written to the trace.
Handlers live in the process: an instance's own (register) and the deployment's, registered once at start-up in
velaris.orchestration.handlers (the engine builds a fresh instance per call, so only those exist there). A task that crashed the process mid-run is marked "started" and needs a
person to decide whether to run it again.
"""
import logging
import time
from typing import Any, Callable, Dict, Optional

from velaris.agentkit.aicore_b_authz import approval_proven
from velaris.agentkit.checks import ident, is_json
from velaris.agentkit.results import fail, health, invalid
from velaris.agentkit.state import JsonState
from velaris.agents.VCAS_SUPERVISOR.main import task_error
from velaris.intel import approvals
from velaris.orchestration import handlers as shared

logger = logging.getLogger("VCAS_AUTOPILOT")
NAME = "VCAS_AUTOPILOT"


_proven = approval_proven      # the one implementation lives in aicore_b_authz (ASEL_EXECUTOR uses it too)


class VCASAutopilotAgent:
    def __init__(self):
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Any]] = {}
        self._runs = JsonState(NAME, "runs.json", {"runs": {}})

    def health_check(self):
        return health(NAME, handlers=self.handlers())

    def register(self, action: str, handler: Callable[[Dict[str, Any]], Any]) -> Dict[str, Any]:
        if ident(action) is None or not callable(handler):
            return invalid("register needs an action name and a callable")
        self._handlers[action] = handler
        return {"status": "ok", "action": action}

    def handlers(self):
        """This instance's handlers and the deployment's (orchestration.handlers): the engine builds a fresh instance per call."""
        return sorted(set(self._handlers) | set(shared.names(NAME)))

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
        handler = self._handlers.get(task["action"]) or shared.get(NAME, task["action"])
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
            run = {"state": "done", "result": output if is_json(output) else repr(output)}
        except Exception as e:      # a handler is outside code: record the failure, never crash the caller
            logger.warning("VCAS_AUTOPILOT: handler for %s failed: %s", task["action"], e)
            run = {"state": "failed", "error": f"{type(e).__name__}: {e}"[:300]}
        run.update(action=task["action"], finished=time.time())
        self._runs.update(lambda s: s["runs"].__setitem__(task_id, run))
        try:
            approvals.audit("VCAS_AUTOPILOT", "executed", request_id=task_id, by=str(task.get("principal") or ""), decision=run["state"],
                            trace_actor=NAME, trace_action="run", task_id=task_id, action=task["action"], state=run["state"])
        except Exception as e:      # the trace is the proof of what ran: without it say so loudly, never report a clean run
            logger.warning("VCAS_AUTOPILOT: run of %s not written to the trace: %s", task_id, e)
            return {**base, **fail("audit_failed", "the task ran (its result is stored under its id and it will not run again) but "
                                   "the run could not be written to the audit trace: an operator must record it"),
                    "executed": run["state"] == "done", "run": run}
        return {**base, "executed": run["state"] == "done", "status": "ok" if run["state"] == "done" else "failed",
                "run": run}
