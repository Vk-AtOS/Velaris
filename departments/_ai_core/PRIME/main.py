"""PRIME: the Velaris controller, and the one place that decides what an agent or person may do.

Two jobs.
1. Authorisation (written fresh for Velaris after the shape of AetherOS Prime):
   authorize(principal, action, resource, context) -> allow / needs_approval / deny
   with a reason, from time-limited grants that people give. The decision is
   pure code over the stored grants (velaris.agentkit.aicore_b_authz): no model,
   fail closed, a NEVER list no grant can open, a hard amount ceiling, and
   anything a grant does not clearly cover goes to the grant's named approver.
   Grants are stored owner-only under this agent's state directory. Every
   grant, revocation, request and decision is written to the hash-chained trace
   before the answer is returned; if the trace cannot be written the answer is deny.
2. Control of the engine (kept from before): system_status(), a self-test
   pipeline, and execute(agent, method), which runs only when a grant allows the
   current caller "agent.execute" on exactly "<AGENT>.<method>" (an explicit
   allowlist; no patterns). Private methods, PRIME itself and governance
   management methods (MANAGEMENT_METHODS) are never run through execute.

Identity comes from the current caller (velaris.core.access), never an argument:
grant() is given by the caller, who must be a governance admin or hold a live,
delegable grant covering everything they pass on (never more than they hold), and
may not grant to themselves; revoke() is for the grantor, the approver or a
governance admin. A legacy grantor/by/principal argument must name the caller.
"""
import logging
import time
from typing import Any, Dict, List, Optional

from velaris.agentkit import aicore_b_authz as authz
from velaris.agentkit.aicore_b_common import JsonState, fail, ident, invalid, new_id, number
from velaris.agents.ENGINE.main import VelarisEngine
from velaris.core.access import GOVERNANCE_ADMINS, check_caller, has_role
from velaris.intel import trace

logger = logging.getLogger("PRIME")
NAME = "PRIME"
# Never run through execute(): they change who may do what, or decide on someone's behalf.
MANAGEMENT_METHODS = frozenset({
    "grant", "revoke", "authorize", "execute", "add_policy", "remove_policy", "replace_policy", "put_policy",
    "retire", "set_approvers", "exempt", "enroll", "issue_token", "set_mandate", "set_principles", "resolve",
    "decide", "approve", "reject", "register", "import_bundle", "set_charter",
})


class VelarisPrime:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._engine = None
        self._grants = JsonState(NAME, "grants.json", {"grants": {}})

    @property
    def engine(self):
        """The agent engine, built on first use (it scans every department)."""
        if self._engine is None:
            self._engine = VelarisEngine()
        return self._engine

    # ---- control -------------------------------------------------------------

    def health_check(self) -> Dict[str, Any]:
        return {"agent": NAME, "status": "ok", "version": "1.0.0", "engine_status": self.engine.health_check(),
                "live_grants": len(authz.live_grants(self._grants.load().get("grants", {}).values(), time.time()))}

    def system_status(self) -> Dict[str, Any]:
        """Diagnostics across PRIME + ENGINE + REGISTRY."""
        return {"prime": self.health_check(), "engine": self.engine.health_check(),
                "agents": self.engine.registry.health_all()}

    def run_simple_self_test(self):
        """Health of the three security agents, through the engine pipeline."""
        return self.engine.pipeline([{"agent": a, "method": "health_check"} for a in ("VIGILIS", "CUSTOS", "PRAETOR")])

    def execute(self, agent: str, method: str, params: Dict[str, Any] = None, principal: Optional[str] = None):
        """Run agent.method(**params) for the current caller, only if a grant names exactly that method.

        Never runs on needs_approval. `principal`, if given, must be the caller."""
        refused = {"decision": authz.DENY, "executed": False, "status": "not_authorised"}
        if not (isinstance(agent, str) and agent.isidentifier() and isinstance(method, str) and method.isidentifier()):
            return {**refused, "reason": "agent and method must be plain names"}
        if method.startswith("_") or agent == NAME or method in MANAGEMENT_METHODS:
            return {**refused, "reason": f"{agent}.{method} cannot be run through PRIME.execute"}
        caller, denied = check_caller(NAME, "execute", {"agent": agent, "method": method}, claimed=principal)
        if denied:
            return {**refused, **denied, "executed": False}
        decision = self.authorize(caller.id, authz.EXECUTE, f"{agent}.{method}", {})
        if decision["decision"] != authz.ALLOW:
            return {**decision, "status": "not_authorised", "executed": False}
        return self.engine.run(agent, method, params)

    # ---- grants --------------------------------------------------------------

    def grant(self, grantor: Optional[str] = None, principal: Optional[str] = None,
              actions: Optional[List[str]] = None, approver: Optional[str] = None, *,
              resources: Optional[List[str]] = None, autonomy: str = "with_approval",
              valid_for_seconds: float = 7 * 86400, max_amount: Optional[float] = None,
              currency: Optional[str] = None, delegable: bool = False, now: Optional[float] = None) -> Dict[str, Any]:
        """Record a grant from the current caller to `principal`. Returns its id, or why it was refused.

        `resources` must be given for a grant covering agent.execute; otherwise it defaults to ["**"]
        (every resource; "*" alone matches one path segment)."""
        start = time.time() if now is None else now
        seconds = number(valid_for_seconds)
        if seconds is None or number(start) is None:
            return invalid("valid_for_seconds and now must be numbers")
        caller, refused = check_caller(NAME, "grant", {"principal": str(principal)[:200], "actions": str(actions)[:500]},
                                       claimed=grantor)
        if refused:
            return refused
        g = {"id": new_id("grant"), "grantor": caller.id, "principal": principal, "actions": actions,
             "resources": resources if resources is not None else ["**"], "autonomy": autonomy,
             "approver": approver, "valid_from": start, "valid_until": start + seconds,
             "revoked_at": None, "revoked_by": None, "delegable": delegable}
        if max_amount is not None:
            g.update(max_amount=max_amount, currency=currency)
        err = authz.grant_error(g)
        if err:
            return invalid(err)
        if not has_role(caller, GOVERNANCE_ADMINS):
            err = authz.delegation_error(self._grants.load().get("grants", {}).values(), g, start)
            if err:
                trace.append(NAME, "prime.grant.refused", {"grantor": caller.id, "principal": principal, "reason": err})
                return fail("denied", err)
        try:
            trace.append(NAME, "prime.grant", {k: v for k, v in g.items() if k not in ("revoked_at", "revoked_by")})
        except OSError as e:
            logger.warning("PRIME: grant not recorded in the trace, so not stored: %s", e)
            return fail("audit_failed", "the grant could not be recorded, so it was not stored")
        self._grants.update(lambda s: s.setdefault("grants", {}).__setitem__(g["id"], g))
        return {"status": "ok", "grant_id": g["id"], "valid_until": g["valid_until"]}

    def revoke(self, grant_id: str, by: Optional[str] = None, now: Optional[float] = None) -> Dict[str, Any]:
        """The grantor, the named approver or a governance admin (the current caller) can revoke a grant.

        Revoked grants stay on record. `by`, if given, must be the caller."""
        when = time.time() if now is None else now
        caller, refused = check_caller(NAME, "revoke", {"grant_id": str(grant_id)[:64]}, claimed=by)
        if refused:
            return refused
        by, admin = caller.id, has_role(caller, GOVERNANCE_ADMINS)

        def change(state):
            g = state.get("grants", {}).get(grant_id)
            if g is None:
                return fail("not_found", f"no grant {grant_id!r}")
            if by not in (g["grantor"], g["approver"]) and not admin:
                return fail("denied", "only the grantor or the approver can revoke a grant")
            if g["revoked_at"] is not None:
                return fail("already_revoked", f"grant {grant_id} was already revoked")
            g["revoked_at"], g["revoked_by"] = when, by
            return {"status": "ok", "grant_id": grant_id, "revoked_at": when}
        result = self._grants.update(change)
        if result["status"] == "ok":
            trace.append(NAME, "prime.revoke", {"grant_id": grant_id, "by": by})
        return result

    def grants(self, principal: Optional[str] = None, live_only: bool = False) -> List[Dict[str, Any]]:
        everything = list(self._grants.load().get("grants", {}).values())
        if live_only:
            everything = authz.live_grants(everything, time.time())
        return sorted((g for g in everything if principal is None or g["principal"] == principal),
                      key=lambda g: g["valid_from"])

    # ---- decisions -----------------------------------------------------------

    def authorize(self, principal: Any, action: Any, resource: Any = None, context: Optional[Dict[str, Any]] = None,
                  now: Optional[float] = None, task_id: Optional[str] = None,
                  params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """allow / needs_approval / deny with a reason. Both the request and the decision are traced first.

        `task_id` (with the task's `params`) ties the decision to one exact piece of work: the decision
        carries authz.task_digest of it, which VCAS_AUTOPILOT checks before running anything."""
        when = time.time() if now is None else now
        digest = None
        if task_id is not None:
            try:
                digest = authz.task_digest({"id": task_id, "action": action, "principal": principal,
                                            "resource": resource, "context": context, "params": params})
            except (TypeError, ValueError) as e:
                logger.warning("PRIME: task %s cannot be digested: %s", task_id, e)
        request = {"principal": principal if ident(principal) else None, "action": action if ident(action) else None,
                   "resource": resource if resource is None or ident(resource) else None,
                   "amount": (context or {}).get("amount") if isinstance(context, dict) else None,
                   "currency": (context or {}).get("currency") if isinstance(context, dict) else None,
                   "task_id": str(task_id) if task_id is not None else None, "task_digest": digest}
        try:
            trace.append(str(request["principal"] or "unknown"), "prime.request", request)
            try:
                decision = authz.authorize(principal, action, resource, context,
                                           grants=self._grants.load().get("grants", {}).values(), now=when)
            except Exception as e:      # a bug in the check must never come out as an allow
                logger.warning("PRIME: authorisation check failed: %s", e)
                decision = {"decision": authz.DENY, "reason": "the check failed; refusing", "grant_id": None,
                            "approver": None, "notify": None}
            entry = trace.append(NAME, "prime.decision", {**request, **decision})
        except OSError as e:
            logger.warning("PRIME: decision could not be recorded: %s", e)
            return {"decision": authz.DENY, "reason": "the decision could not be recorded; refusing",
                    "grant_id": None, "approver": None, "notify": None, "status": "audit_failed"}
        return {**decision, "status": "ok", "trace_hash": entry["hash"]}


class PrimeAgent(VelarisPrime):
    """Backward-compatible alias (test_phase4_intel.py and integration tests use this name)."""
