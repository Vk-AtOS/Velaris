"""EACPE_HUMAN_GUARD: irreversible actions wait for a named person.

Action classes are declared guarded (with the people who may approve them) or
exempt. validate(action) answers for one concrete action, {"class": ...,
"requested_by": ..., <any details>}:

  exempt class          approved, nothing to wait for
  guarded class         approved only if a listed approver - not the requester -
                        approved this exact action (its details are hashed),
                        within APPROVAL_TTL_S. An approval is used once.
  any other class       refused as "unclassified": an action nobody classified is
                        not assumed to be safe
  malformed             refused

Who acts is never an argument: the requester, the approver and whoever changes a class
are the current caller (velaris.core.access). request() and decide() refuse without one;
set_approvers() and exempt() also need the governance admin role. Lifting the guard from a class that is guarded
(exempt() on it) needs TWO different governance admins: the first call records a proposal, a second admin's call within
APPROVAL_TTL_S makes it exempt, so one admin cannot switch off the approval of an irreversible action alone. A legacy `by` /
`approver` / `requested_by` value is accepted only when it is the caller's own id.

Out of the box, DEFAULT_GUARDED classes are guarded with no approvers, so they
cannot proceed until someone is named with set_approvers(). Requests, decisions
and use of an approval are recorded in the hash-chained trace; an approval that
cannot be recorded does not count.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import is_json, is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.agentkit.infra_store import audit
from velaris.core.access import GOVERNANCE_ADMINS, check_caller

NAME = "EACPE_HUMAN_GUARD"
APPROVAL_TTL_S = 24 * 3600
DEFAULT_GUARDED = ("delete_data", "transfer_funds", "deploy_production", "send_external", "revoke_access",
                   "sign_contract")


def action_hash(action: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(action, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class EACPE_HUMAN_GUARDAgent:
    def __init__(self) -> None:
        self.name = NAME
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def _classes(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return data.get("classes") or {c: {"mode": "guarded", "approvers": []} for c in DEFAULT_GUARDED}

    def set_approvers(self, action_class: str, approvers: List[str], by: Optional[str] = None) -> Dict[str, Any]:
        """Guard `action_class`; only the listed people may approve it. Governance admins only."""
        if not is_name(action_class) or not isinstance(approvers, list) or not all(is_name(a) for a in approvers):
            return invalid("need a class name and a list of approver names")
        caller, refused = check_caller(NAME, "set_approvers", {"class": action_class, "approvers": approvers},
                                       roles=GOVERNANCE_ADMINS, claimed=by)
        if refused:
            return refused
        by = caller.id
        if not audit(NAME, "class.guarded", {"class": action_class, "approvers": approvers, "by": by}):
            return fail("audit_failed", "the change could not be recorded, so it was not made")
        self._state.update(lambda d: (d.__setitem__("classes", {**self._classes(d), action_class: {"mode": "guarded", "approvers": approvers}}),
                                      d.get("exempt_proposals", {}).pop(action_class, None)))
        return ok(action_class=action_class, approvers=approvers)

    def exempt(self, action_class: str, by: Optional[str] = None) -> Dict[str, Any]:
        """Declare a class reversible: its actions need no approval. Governance admins only."""
        if not is_name(action_class):
            return invalid("need a class name")
        caller, refused = check_caller(NAME, "exempt", {"class": action_class}, roles=GOVERNANCE_ADMINS, claimed=by)
        if refused:
            return refused
        by = caller.id
        now = time.time()

        def apply(d: Dict[str, Any]) -> Dict[str, Any]:
            if self._classes(d).get(action_class, {}).get("mode") == "guarded":      # lifting a guard needs a second person
                prop = d.get("exempt_proposals", {}).get(action_class)
                if prop is None or now - prop["ts"] > APPROVAL_TTL_S or prop["by"] == by:
                    if not audit(NAME, "class.exempt_proposed", {"class": action_class, "by": by}):
                        return fail("audit_failed", "the proposal could not be recorded")
                    d.setdefault("exempt_proposals", {})[action_class] = {"by": by, "ts": now}
                    return {"status": "pending_second_person", "action_class": action_class, "proposed_by": by,
                            "reason": "a different governance admin must repeat this call to lift the guard"}
            if not audit(NAME, "class.exempt", {"class": action_class, "by": by}):
                return fail("audit_failed", "the change could not be recorded, so it was not made")
            d.get("exempt_proposals", {}).pop(action_class, None)
            d["classes"] = {**self._classes(d), action_class: {"mode": "exempt", "approvers": []}}
            return ok(action_class=action_class, mode="exempt")
        return self._state.update(apply)

    @staticmethod
    def _shape(action: Any) -> str:
        if not isinstance(action, dict) or not is_name(action.get("class")) or not is_name(action.get("requested_by")):
            return "action must be an object with 'class' and 'requested_by'"
        return "" if is_json(action) else "action must be JSON"

    def request(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Ask for approval of one action, as the current caller. Returns the request id the approver acts on."""
        if isinstance(action, dict) and "requested_by" not in action:
            caller, refused = check_caller(NAME, "request", {"class": str(action.get("class"))[:128]})
            if refused:
                return refused
            action = {**action, "requested_by": caller.id}
        problem = self._shape(action)
        if problem:
            return invalid(problem)
        _, refused = check_caller(NAME, "request", {"class": action["class"]}, claimed=action["requested_by"])
        if refused:
            return refused
        cls = self._classes(self._state.load()).get(action["class"])
        if cls is None or cls["mode"] != "guarded":
            return fail("not_guarded", "this class is exempt or unclassified; nothing to approve")
        rid = uuid.uuid4().hex
        entry = {"action": action, "hash": action_hash(action), "state": "pending", "ts": time.time()}
        if not audit(NAME, "request", {"id": rid, "class": action["class"], "by": action["requested_by"], "hash": entry["hash"]}):
            return fail("audit_failed", "the request could not be recorded, so it was not made")
        self._state.update(lambda d: d.setdefault("requests", {}).__setitem__(rid, entry))
        return {"status": "pending", "request_id": rid, "approvers": cls["approvers"], "action_hash": entry["hash"]}

    def decide(self, request_id: str, approver: Optional[str] = None, approve: Optional[bool] = None,
               now: Optional[float] = None) -> Dict[str, Any]:
        """The current caller approves or rejects a request. `approver`, if given, must be the caller."""
        if not isinstance(approve, bool) or (now is not None and not is_number(now, 0)):
            return invalid("approve must be true or false")
        caller, refused = check_caller(NAME, "decide", {"id": str(request_id)[:64], "approve": approve},
                                       claimed=approver)
        if refused:
            return refused
        approver = caller.id
        now = time.time() if now is None else now

        def apply(data: Dict[str, Any]) -> Dict[str, Any]:
            req = data.get("requests", {}).get(request_id) if isinstance(request_id, str) else None
            if req is None:
                return fail("unknown_request", "no such request")
            if req["state"] != "pending":
                return fail("denied", f"request is already {req['state']}")
            cls = self._classes(data).get(req["action"]["class"], {})
            if approver not in cls.get("approvers", []):
                return fail("denied", f"{approver} is not a named approver for {req['action']['class']}")
            if approver == req["action"]["requested_by"]:
                return fail("denied", "the requester cannot approve their own action")
            recorded = audit(NAME, "decision", {"id": request_id, "approver": approver, "approve": approve})
            if not recorded:
                return fail("error", "the decision could not be recorded; nothing changed")
            req.update(state="approved" if approve else "rejected", approver=approver, decided_at=now, trace=recorded)
            return ok(request_id=request_id, state=req["state"])
        return self._state.update(apply)

    def validate(self, action: dict, now: Optional[float] = None) -> Dict[str, Any]:
        """May this exact action go ahead now? Consumes the approval it relies on (the requester, as the current caller, only)."""
        def no(status: str, reason: str) -> Dict[str, Any]:
            return {"approved": False, "action": action, "status": status, "reason": reason}
        problem = self._shape(action)
        if problem or (now is not None and not is_number(now, 0)):
            return no("invalid_input", problem or "now must be a timestamp")
        now = time.time() if now is None else now

        def check(data: Dict[str, Any]) -> Dict[str, Any]:
            cls = self._classes(data).get(action["class"])
            if cls is None:
                return no("unclassified", "this action class is neither guarded nor exempt")
            if cls["mode"] == "exempt":
                return {"approved": True, "action": action, "status": "ok", "reason": "class is exempt"}
            _, refused = check_caller(NAME, "validate", {"class": action["class"]}, claimed=action["requested_by"])
            if refused:                                # a single-use approval is spent only by the person who asked for it
                return no(refused["status"], refused["reason"])
            digest = action_hash(action)
            for rid, req in sorted(data.get("requests", {}).items(), key=lambda kv: kv[1]["ts"]):
                if req["hash"] == digest and req["state"] == "approved":
                    if now - req["decided_at"] > APPROVAL_TTL_S:
                        req["state"] = "expired"
                        continue
                    _, refused = check_caller(NAME, "use_approval", {"id": rid, "hash": digest},
                                              claimed=action["requested_by"])
                    if refused:
                        return no(refused["status"], "only the requester, as an authenticated caller, may use an approval: "
                                  + refused["reason"])
                    if not audit(NAME, "approval.used", {"id": rid, "hash": digest}):
                        return no("error", "use of the approval could not be recorded")
                    req.update(state="used", used_at=now)
                    return {"approved": True, "action": action, "status": "ok", "approver": req["approver"],
                            "request_id": rid, "reason": f"approved by {req['approver']}"}
            return no("pending_approval", "no unused approval by a named approver for this exact action")
        return self._state.update(check)
