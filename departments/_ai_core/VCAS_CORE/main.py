"""VCAS_CORE: submit a task, and it runs on autopilot only when it is allowed to.

submit(task):
  1. VCAS_ROUTER: is there an autopilot handler?    no  -> "manual"
  2. VCAS_SUPERVISOR (PRIME): may it run?            deny -> "denied"
                                                     needs_approval -> "pending" (stored, names the approver)
  3. VCAS_AUTOPILOT runs it                          -> "done" / "failed"
decide(task_id, approve, by) settles a pending task: only the approver PRIME
named can decide; an approval runs the task, a rejection closes it. Pending
tasks are stored owner-only under this agent's state directory and survive a
restart (handlers must be registered again on the new autopilot instance).
"""
import time
from typing import Any, Dict, Optional

from velaris.agentkit.aicore_b_common import JsonState, fail, health, ident, invalid
from velaris.agents.VCAS_AUTOPILOT.main import VCASAutopilotAgent
from velaris.agents.VCAS_ROUTER.main import VCASRouterAgent
from velaris.agents.VCAS_SUPERVISOR.main import VCASSupervisorAgent
from velaris.intel import trace

NAME = "VCAS_CORE"


class VCASCoreAgent:
    def __init__(self, autopilot: Optional[VCASAutopilotAgent] = None,
                 supervisor: Optional[VCASSupervisorAgent] = None):
        self.router = VCASRouterAgent()
        self.supervisor = supervisor or VCASSupervisorAgent()
        self.autopilot = autopilot or VCASAutopilotAgent()
        self._pending = JsonState(NAME, "pending.json", {"pending": {}})

    def health_check(self):
        return health(NAME, pending=len(self._pending.load().get("pending", {})))

    def submit(self, task: Any, now: Optional[float] = None) -> Dict[str, Any]:
        routed = self.router.route(task, self.autopilot.handlers())
        if routed["autopilot_route"] != "ok":
            return {"status": routed["status"], "outcome": "manual", "reason": routed["reason"]}
        verdict = self.supervisor.approve(task, now=now)
        if verdict["decision"] == "needs_approval":
            entry = {"task": task, "approver": verdict["approver"], "reason": verdict["reason"], "ts": time.time()}
            self._pending.update(lambda s: s.setdefault("pending", {}).__setitem__(str(task["id"]), entry))
            return {"status": "pending", "outcome": "pending", "approver": verdict["approver"],
                    "reason": verdict["reason"]}
        if not verdict["approved"]:
            return {"status": "denied", "outcome": "denied", "reason": verdict["reason"]}
        ran = self.autopilot.execute(task, {"trace_hash": verdict.get("trace_hash")})
        return {"status": ran["status"], "outcome": "done" if ran["executed"] else ran["status"],
                "run": ran.get("run"), "reason": verdict["reason"]}

    def pending(self) -> Dict[str, Any]:
        return self._pending.load().get("pending", {})

    def decide(self, task_id: str, approve: bool, by: str, note: str = "") -> Dict[str, Any]:
        entry = self.pending().get(str(task_id))
        if entry is None:
            return fail("not_found", f"no pending task {task_id!r}")
        if ident(by) is None or by != entry["approver"]:
            return fail("denied", f"only {entry['approver']} can decide this task")
        if not isinstance(approve, bool):
            return invalid("approve must be true or false")
        self._pending.update(lambda s: s["pending"].pop(str(task_id), None))
        recorded = trace.append(NAME, "decision", {"task_id": str(task_id), "approved": approve, "by": by,
                                                   "note": str(note)[:300]})
        if not approve:
            return {"status": "rejected", "outcome": "rejected", "by": by}
        ran = self.autopilot.execute(entry["task"], {"trace_hash": recorded["hash"]})
        return {"status": ran["status"], "outcome": "done" if ran["executed"] else ran["status"],
                "run": ran.get("run"), "by": by}
