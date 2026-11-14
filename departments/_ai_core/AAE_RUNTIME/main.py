"""AAE runtime: runs one approved action, once, and keeps a record of it.

An action is {"id", "type", "params"?}. run() asks AAE_POLICY first: a denied
action does not run. One that needs approval goes through two people
(velaris.core.access gives who the current caller is):

  1. run(action) by the requester records a request (requested_by = the caller,
     and a digest of the action) and returns needs_approval. With no caller,
     nothing is recorded and the action can never be approved as it stands.
  2. run(action, approved_by=...) by someone else runs it. `approved_by` must be
     the caller's own id; the requester cannot approve their own request; the
     action must be exactly the one requested (same digest); and there must be
     a recorded request.
The handler for the action type is a Python callable registered by the caller.
An action id that already completed is not run again; the recorded result is
returned (`replayed`). Every attempt goes to the journal and to the hash-chained
trace in velaris.intel.trace (action type and outcome, not the parameters).
State (journal by action id): <VELARIS_DATA>/agents/AAE_RUNTIME/state.json.
"""
import hashlib
import json
import logging
import time

from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.agents.AAE_POLICY.main import AAE_POLICYAgent
from velaris.core.access import check_caller
from velaris.intel import trace

NAME = "AAE_RUNTIME"
logger = logging.getLogger(NAME)


def _digest(action):
    return hashlib.sha256(json.dumps(action, sort_keys=True, default=str).encode()).hexdigest()


class AAE_RUNTIMEAgent:
    def __init__(self, policy=None):
        self.policy = policy or AAE_POLICYAgent()
        self.handlers = {}
        self._state = JsonState(NAME, "state.json", {"journal": {}, "requests": {}})

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
        if done and done["outcome"] == "in_progress":
            return fail("in_progress", "this action id is running or died mid-run; it is not run twice", action=aid)
        if done and done["outcome"] == "done":
            if done.get("digest") != _digest(action):      # same id, different action: never hand back the old result
                return fail("id_conflict", "this action id already completed for a different action", action=aid)
            return ok(action=aid, result=done["result"], replayed=True, approved_by=done["approved_by"])
        verdict = self.policy.decide(action)
        if verdict["decision"] == "deny":
            return self._finish(aid, atype, "denied", fail("denied", verdict["reason"], action=aid))
        requested_by = None
        if verdict["decision"] == "needs_approval":
            digest = _digest(action)
            if ident(approved_by) is None:
                return self._request(aid, atype, digest, verdict["reason"])
            caller, refused = check_caller(NAME, "approve", {"action": aid, "type": atype}, claimed=approved_by)
            if refused:
                return {**refused, "action": aid}
            request = self._state.load().get("requests", {}).get(aid)
            if request is None or request["digest"] != digest:
                return fail("no_request", "approve an action someone requested, exactly as requested", action=aid)
            if request["requested_by"] == caller.id:
                trace.append(NAME, "approval.refused", {"action": aid, "type": atype, "caller": caller.id})
                return fail("denied", "the person who requested an action cannot approve it", action=aid)
            approved_by, requested_by = caller.id, request["requested_by"]
        else:
            approved_by = None              # nothing needed approving; do not record a claimed approver
        handler = self.handlers.get(atype)
        if handler is None:
            return self._finish(aid, atype, "no_handler",
                                fail("no_handler", f"no handler registered for {atype!r}", action=aid),
                                approved_by, requested_by)
        # Claim the id before the handler runs, so a second caller or a crash cannot run it twice.
        def claim(data):
            if data["journal"].get(aid, {}).get("outcome") in ("in_progress", "done"):
                return False
            data["journal"][aid] = {"type": atype, "outcome": "in_progress", "at": time.time(),
                                    "approved_by": approved_by, "requested_by": requested_by,
                                    "result": None, "reason": None, "digest": _digest(action)}
            return True
        if not self._state.update(claim):
            return fail("in_progress", "this action id is already running or completed", action=aid)
        try:
            result = handler(action.get("params") or {})
        except Exception as e:      # handlers are caller code: report the failure, do not crash the runtime
            logger.warning("action %s (%s) failed: %s", aid, atype, e)
            return self._finish(aid, atype, "failed", fail("failed", f"{type(e).__name__}: {e}", action=aid),
                                approved_by, requested_by)
        return self._finish(aid, atype, "done",
                            ok(action=aid, result=result, replayed=False, approved_by=approved_by,
                               requested_by=requested_by), approved_by, requested_by, _digest(action))

    def _request(self, aid, atype, digest, reason):
        """Record who asked for an action that needs approval. Nothing is recorded without a caller."""
        caller, refused = check_caller(NAME, "request", {"action": aid, "type": atype})
        if refused:
            return fail("needs_approval", reason, action=aid, requested_by=None)
        request = {"requested_by": caller.id, "digest": digest, "at": time.time()}
        self._state.update(lambda data: data.setdefault("requests", {}).update({aid: request}))
        return fail("needs_approval", reason, action=aid, requested_by=caller.id)

    def _finish(self, aid, atype, outcome, response, approved_by=None, requested_by=None, digest=None):
        entry = {"type": atype, "outcome": outcome, "at": time.time(), "approved_by": approved_by,
                 "requested_by": requested_by, "result": response.get("result"), "reason": response.get("reason"),
                 "digest": digest}

        def record(data):
            data["journal"][aid] = entry
            if outcome == "done":
                data.setdefault("requests", {}).pop(aid, None)
        self._state.update(record)
        trace.append(NAME, f"action.{outcome}", {"action": aid, "type": atype, "approved_by": approved_by,
                                                 "requested_by": requested_by})
        return response

    def history(self, action_id):
        entry = self._state.load()["journal"].get(action_id) if isinstance(action_id, str) else None
        return ok(action=action_id, **entry) if entry else fail("not_found", f"no record of action {action_id!r}")
