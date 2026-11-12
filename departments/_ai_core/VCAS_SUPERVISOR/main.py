"""VCAS_SUPERVISOR: says whether a task may run, by asking PRIME.

VCAS is read here as "Velaris controlled autopilot": VCAS_ROUTER decides
whether a task can run on autopilot at all, VCAS_SUPERVISOR decides whether it
is allowed, VCAS_AUTOPILOT runs it, VCAS_CORE runs the whole flow including
waiting for a person.

This agent holds no rules of its own: approve(task) is PRIME.authorize for the
task's principal, action, resource and context. approved is True only for
"allow"; "needs_approval" names the person who must decide; anything else is a
refusal.

task: {"id", "action", "principal", "resource" (optional), "context": {"amount", "currency"} (optional),
       "params": {...} (optional)}
"""
from typing import Any, Dict, Optional

from velaris.agentkit.checks import ident, is_json
from velaris.agentkit.results import health, invalid
from velaris.agents.PRIME.main import VelarisPrime

NAME = "VCAS_SUPERVISOR"


def task_error(task: Any) -> Optional[str]:
    if not isinstance(task, dict):
        return "a task must be an object with 'id', 'action' and 'principal'"
    for key in ("id", "action", "principal"):
        if ident(str(task.get(key) or "")) is None:
            return f"the task needs '{key}'"
    if task.get("context") is not None and not isinstance(task["context"], dict):
        return "'context' must be an object"
    if task.get("params") is not None and not isinstance(task["params"], dict):
        return "'params' must be an object"
    if not is_json({k: task.get(k) for k in ("resource", "context", "params")}):
        return "'resource', 'context' and 'params' must be JSON"
    return None


class VCASSupervisorAgent:
    def __init__(self, prime: Optional[VelarisPrime] = None):
        self.prime = prime or VelarisPrime()

    def health_check(self):
        return health(NAME)

    def approve(self, task: Any, now: Optional[float] = None) -> Dict[str, Any]:
        err = task_error(task)
        if err:
            return {"approved": False, "task": task, "decision": "deny", **invalid(err)}
        d = self.prime.authorize(task["principal"], task["action"], task.get("resource"), task.get("context") or {},
                                 now=now, task_id=str(task["id"]), params=task.get("params") or {})
        return {"approved": d["decision"] == "allow", "task": task, **d}
