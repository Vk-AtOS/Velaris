"""AAE runtime: runs one approved action, once, and keeps a record of it.

An action is {"id", "type", "params"?}. run() asks AAE_POLICY first: a denied
action does not run, and one that needs approval runs only with `approved_by`.
The handler for the action type is a Python callable registered by the caller.
An action id that already completed is not run again; the recorded result is
returned (`replayed`). Every attempt goes to the journal and to the hash-chained
trace in velaris.intel.trace (action type and outcome, not the parameters).
State (journal by action id): <VELARIS_DATA>/agents/AAE_RUNTIME/state.json.
"""
import logging
import time

from velaris.agentkit.aicore_a_common import JsonState, fail, health, ident, invalid, ok
from velaris.agents.AAE_POLICY.main import AAE_POLICYAgent
from velaris.intel import trace
from velaris.intel.paths import agent_dir

NAME = "AAE_RUNTIME"
logger = logging.getLogger(NAME)


class AAE_RUNTIMEAgent:
    def __init__(self, policy=None):
        self.policy = policy or AAE_POLICYAgent()
        self.handlers = {}
        self._state = JsonState(lambda: agent_dir(NAME) / "state.json", {"journal": {}})

    def health_check(self):
        return health(NAME, handlers=sorted(self.handlers))

    def register(self, action_type, handler):
        if ident(action_type) is None or not callable(handler):
            return invalid("action_type must be a name and handler a callable")
        self.handlers[action_type] = handler
        return ok(registered=action_type)

    def run(self, action, approved_by=None):
        if not isinstance(action, dict) or ident(action.get("id")) is None or ident(action.get("type")) is None:
            return invalid("action must be an object with an 'id' and a 'type'")
        aid, atype = action["id"], action["type"]
        done = self._state.load()["journal"].get(aid)
        if done and done["outcome"] == "done":
            return ok(action=aid, result=done["result"], replayed=True, approved_by=done["approved_by"])
        verdict = self.policy.decide(action)
        if verdict["decision"] == "deny":
            return self._finish(aid, atype, "denied", fail("denied", verdict["reason"], action=aid))
        if verdict["decision"] == "needs_approval" and ident(approved_by) is None:
            return fail("needs_approval", verdict["reason"], action=aid)       # not journalled: nothing happened
        handler = self.handlers.get(atype)
        if handler is None:
            return self._finish(aid, atype, "no_handler",
                                fail("no_handler", f"no handler registered for {atype!r}", action=aid))
        try:
            result = handler(action.get("params") or {})
        except Exception as e:      # handlers are caller code: report the failure, do not crash the runtime
            logger.warning("action %s (%s) failed: %s", aid, atype, e)
            return self._finish(aid, atype, "failed", fail("failed", f"{type(e).__name__}: {e}", action=aid))
        return self._finish(aid, atype, "done",
                            ok(action=aid, result=result, replayed=False, approved_by=approved_by), approved_by)

    def _finish(self, aid, atype, outcome, response, approved_by=None):
        entry = {"type": atype, "outcome": outcome, "at": time.time(), "approved_by": approved_by,
                 "result": response.get("result"), "reason": response.get("reason")}
        self._state.update(lambda data: data["journal"].update({aid: entry}))
        trace.append(NAME, f"action.{outcome}", {"action": aid, "type": atype, "approved_by": approved_by})
        return response

    def history(self, action_id):
        entry = self._state.load()["journal"].get(action_id) if isinstance(action_id, str) else None
        return ok(action=action_id, **entry) if entry else fail("not_found", f"no record of action {action_id!r}")
