"""ZERO_TRUST_PIPELINE: every request is checked for identity, device, context and policy; the default is deny.

evaluate(request) runs these stages in order and stops at the first that fails:

  1. shape      the request names a subject, a token, a resource and an action
  2. identity   the subject is enrolled and active, and the token was issued to
                that subject and has not expired (HMAC tokens signed with this
                agent's own key, so no SECURE_ACTION_TOKENS.generate() call, for
                any purpose string, can produce one)
  3. policy     among the policies whose resource pattern, action and role match:
                  - a "deny" policy whose device/context conditions hold refuses
                  - otherwise at least one "allow" policy must have every one of
                    its device and context conditions satisfied
  4. record     the decision is written to the hash-chained trace; if it cannot
                be recorded, the answer is deny

Roles come from enrolment, never from the request. Enrolment, revocation and policy
changes need a security admin caller (velaris.core.access); issue_token(subject) gives
a token only to the subject themselves or to a security admin. Every change is traced.

Resources are "/"-separated names. A resource holding "..", an empty segment, a
backslash or NUL is denied; policy patterns match segment by segment ("*" never
crosses "/", a final "**" matches the rest). Device and context facts are
supplied by the enforcement point that calls this agent; conditions over them
use velaris.agentkit.conditions (an absent field never satisfies an allow policy's
condition and always satisfies a deny policy's).
No policy, an unknown subject, a malformed request: all deny.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from velaris.agentkit import conditions
from velaris.agentkit.checks import is_name
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.agentkit.infra_store import audit
from velaris.agents.SECURE_ACTION_TOKENS.main import SecureActionTokens
from velaris.core.access import SECURITY_ADMINS, check_caller, resource_error, resource_matches
from velaris.intel.paths import agent_dir, load_or_create_key

logger = logging.getLogger("ZERO_TRUST_PIPELINE")
NAME = "ZERO_TRUST_PIPELINE"
TOKEN_TTL_S = 900
TOKEN_PURPOSE = "zt-identity/"


class _IdentityTokens(SecureActionTokens):
    """SecureActionTokens' format, signed with a key only this agent holds (domain separation)."""

    def __init__(self) -> None:          # deliberately not super(): never load the shared key
        self.ttl = TOKEN_TTL_S
        self.key = load_or_create_key(agent_dir(NAME) / "identity.key", 32)


def _names(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v for v in value)


class ZERO_TRUST_PIPELINEAgent:
    def __init__(self) -> None:
        self.name = NAME
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    # ── identity ─────────────────────────────────────────────────────────────
    def enroll(self, subject: str, roles: List[str]) -> Dict[str, Any]:
        if not is_name(subject) or ":" in subject or not _names(roles):
            return invalid("subject must be a short name without ':' and roles a non-empty list of names")
        _, refused = check_caller(NAME, "enroll", {"subject": subject, "roles": roles}, roles=SECURITY_ADMINS)
        if refused:
            return refused
        self._state.update(lambda d: d.setdefault("subjects", {}).__setitem__(subject, {"roles": roles, "active": True}))
        return ok(subject=subject, roles=roles)

    def revoke(self, subject: str) -> Dict[str, Any]:
        _, refused = check_caller(NAME, "revoke", {"subject": str(subject)[:128]}, roles=SECURITY_ADMINS)
        if refused:
            return refused
        def off(data: Dict[str, Any]) -> bool:
            s = data.get("subjects", {}).get(subject) if isinstance(subject, str) else None
            if s is not None:
                s["active"] = False
            return s is not None
        return ok(subject=subject, active=False) if self._state.update(off) else fail("unknown_subject", "not enrolled")

    def _subject(self, subject: Any) -> Dict[str, Any]:
        s = self._state.load().get("subjects", {}).get(subject) if isinstance(subject, str) else None
        return s if s and s["active"] else {}

    def issue_token(self, subject: str) -> Dict[str, Any]:
        """A token proving `subject` for TOKEN_TTL_S seconds, for the subject themselves or a security admin.

        Only for enrolled, active subjects."""
        if not isinstance(subject, str):
            return invalid("subject must be a name")
        _, refused = check_caller(NAME, "issue_token", {"subject": subject[:128]}, roles=SECURITY_ADMINS, also=subject)
        if refused:
            return refused
        if not self._subject(subject):
            return fail("denied", "subject is not enrolled or has been revoked")
        return ok(token=_IdentityTokens().generate(TOKEN_PURPOSE + subject), expires_in_s=TOKEN_TTL_S)

    def verify(self, token: str, subject: str = "") -> bool:
        """True only if `token` was issued to the enrolled, active `subject` and is unexpired."""
        if not isinstance(token, str) or not self._subject(subject):
            if not subject:
                logger.warning("verify denied: a token is only valid for a named subject")
            return False
        return _IdentityTokens().validate(token, TOKEN_PURPOSE + subject)["status"] == "OK"

    # ── policy ───────────────────────────────────────────────────────────────
    def add_policy(self, policy_id: str, policy: Dict[str, Any]) -> Dict[str, Any]:
        """{"effect": "allow"|"deny", "resources": [glob], "actions": [...], "roles": [...],
        "device": {conditions}, "context": {conditions}}. Device and context default to no conditions."""
        if not is_name(policy_id) or not isinstance(policy, dict):
            return invalid("policy_id must be a short name and policy an object")
        problems = []
        if policy.get("effect") not in ("allow", "deny"):
            problems.append("effect must be 'allow' or 'deny'")
        problems += [f"{k} must be a non-empty list of names" for k in ("resources", "actions", "roles")
                     if not _names(policy.get(k))]
        for part in ("device", "context"):
            problems += [f"{part}: {p}" for p in conditions.problems(policy.get(part, {}))]
        if _names(policy.get("resources")):
            problems += [f"resource pattern {p!r}: {resource_error(p.replace('**', 'x'))}"
                         for p in policy["resources"] if resource_error(p.replace("**", "x"))]
        problems += [f"unknown field {k}" for k in policy
                     if k not in ("effect", "resources", "actions", "roles", "device", "context")]
        if problems:
            return invalid("; ".join(problems))
        _, refused = check_caller(NAME, "add_policy", {"policy_id": policy_id, "policy": policy}, roles=SECURITY_ADMINS)
        if refused:
            return refused
        stored = {"device": {}, "context": {}, **policy}
        self._state.update(lambda d: d.setdefault("policies", {}).__setitem__(policy_id, stored))
        return ok(policy_id=policy_id)

    def remove_policy(self, policy_id: str) -> Dict[str, Any]:
        _, refused = check_caller(NAME, "remove_policy", {"policy_id": str(policy_id)[:128]}, roles=SECURITY_ADMINS)
        if refused:
            return refused
        gone = self._state.update(lambda d: d.get("policies", {}).pop(policy_id, None)) if isinstance(policy_id, str) else None
        return ok(policy_id=policy_id) if gone else fail("unknown_policy", "no such policy")

    def _decide(self, request: Any) -> Dict[str, Any]:
        if not isinstance(request, dict) or not all(
                isinstance(request.get(k), str) and request[k] for k in ("subject", "token", "resource", "action")):
            return {"decision": "deny", "stage": "shape", "policy_id": None,
                    "reasons": ["request needs subject, token, resource and action"]}
        if resource_error(request["resource"]):
            return {"decision": "deny", "stage": "shape", "policy_id": None,
                    "reasons": [str(resource_error(request["resource"]))]}
        facts = {"device": request.get("device", {}), "context": request.get("context", {})}
        if not all(isinstance(v, dict) for v in facts.values()):
            return {"decision": "deny", "stage": "shape", "policy_id": None,
                    "reasons": ["device and context must be objects"]}
        subject = self._subject(request["subject"])
        if not subject or not self.verify(request["token"], request["subject"]):
            return {"decision": "deny", "stage": "identity", "policy_id": None,
                    "reasons": ["unknown or revoked subject" if not subject else "token is invalid, expired or not this subject's"]}
        allowed_by, near = None, []
        for pid, pol in sorted(self._state.load().get("policies", {}).items()):
            if not (any(resource_matches(pat, request["resource"]) for pat in pol["resources"])
                    and request["action"] in pol["actions"] and set(pol["roles"]) & set(subject["roles"])):
                continue
            failed = [f"{part}.{f}" for part in ("device", "context")
                      for f in conditions.evaluate(pol[part], facts[part], pol["effect"])[1]]
            if pol["effect"] == "deny" and not failed:
                return {"decision": "deny", "stage": "policy", "policy_id": pid, "reasons": [f"denied by policy {pid}"]}
            if pol["effect"] == "allow" and not failed and allowed_by is None:
                allowed_by = pid
            elif pol["effect"] == "allow" and failed:
                near.append(f"{pid}: unmet {', '.join(failed)}")
        if allowed_by:
            return {"decision": "allow", "stage": "policy", "policy_id": allowed_by, "reasons": [f"allowed by policy {allowed_by}"]}
        return {"decision": "deny", "stage": "policy", "policy_id": None,
                "reasons": near or ["no policy allows this subject, resource and action"]}

    def evaluate(self, request: Dict[str, Any]) -> Dict[str, Any]:
        result = self._decide(request)
        safe = request if isinstance(request, dict) else {}
        recorded = audit(NAME, "decision", {"subject": str(safe.get("subject"))[:128], "resource": str(safe.get("resource"))[:256],
                                            "action": str(safe.get("action"))[:64], "decision": result["decision"],
                                            "stage": result["stage"], "policy_id": result["policy_id"]})
        if not recorded:
            result = {"decision": "deny", "stage": "record", "policy_id": None,
                      "reasons": ["the decision could not be recorded in the trace"]}
        return {"status": "ok", "allowed": result["decision"] == "allow", **result, "trace_hash": recorded}
