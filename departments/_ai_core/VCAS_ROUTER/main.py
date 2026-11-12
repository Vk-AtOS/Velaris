"""VCAS_ROUTER: can this task run on autopilot at all?

route(task, handlers) answers "autopilot" when the task is well formed and a
handler for its action is registered with the autopilot, and "manual"
otherwise (with the reason): unknown work goes to a person, never to a
default handler. It does not decide whether the task is allowed; that is
VCAS_SUPERVISOR's job. `handlers` defaults to the actions registered on a
new VCAS_AUTOPILOT, which has none.
"""
from typing import Any, Dict, Iterable, Optional

from velaris.agentkit.results import health
from velaris.agents.VCAS_SUPERVISOR.main import task_error

NAME = "VCAS_ROUTER"


class VCASRouterAgent:
    def health_check(self):
        return health(NAME)

    def route(self, task: Any, handlers: Optional[Iterable[str]] = None) -> Dict[str, Any]:
        """Returns autopilot_route "ok" (with the handler) or "manual" (with the reason)."""
        err = task_error(task)
        if err:
            return {"autopilot_route": "manual", "handler": None, "task": task, "status": "invalid_input",
                    "reason": err}
        known = set(handlers or [])
        if task["action"] not in known:
            return {"autopilot_route": "manual", "handler": None, "task": task, "status": "manual",
                    "reason": f"no autopilot handler is registered for '{task['action']}'"}
        return {"autopilot_route": "ok", "handler": task["action"], "task": task, "status": "ok"}
