"""Deterministic authorisation: (principal, action, resource, context) -> allow / needs_approval / deny.

`authorize` is a pure function over stored grants: no I/O, no model. It fails
closed. `allow` is reached only through a live, unrevoked grant that names the
principal, covers the action and the resource, and whose limit covers the
amount. Anything a live grant does not clearly cover goes to a person
(`needs_approval`, with the grant's approver); anything nobody granted, or
that no grant may ever allow, is denied.

A grant is a time-limited statement by a person (the grantor):

    {"id", "grantor", "principal", "actions": ["invoice.approve", "leave.*"],
     "resources": ["finance/*"], "max_amount": 50000, "currency": "INR",
     "autonomy": "act" | "act_and_notify" | "with_approval" | "observe",
     "approver": "<person asked when the grant does not cover a request>",
     "valid_from": <epoch s>, "valid_until": <epoch s>, "revoked_at", "revoked_by"}
"""
from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Any, Dict, Iterable, List, Optional

from velaris.agentkit.aicore_b_common import ident, number

ALLOW, NEEDS_APPROVAL, DENY = "allow", "needs_approval", "deny"
CURRENCY = "INR"                     # ponytail: one currency, no FX; other currencies go to a person
HARD_CEILING = 500_000.0             # no grant can allow a single amount above this
MAX_GRANT_SECONDS = 30 * 86400.0

# Action types the check understands. True = monetary (needs an amount and a grant limit).
ACTION_TYPES: Dict[str, bool] = {
    "leave.approve": False, "deploy.staging": False, "report.generate": False,
    "message.send": False, "task.run": False, "agent.execute": False,
    "invoice.approve": True, "expense.approve": True, "payment.execute": True,
}
# Refused whatever any grant says.
NEVER = frozenset({
    "person.terminate", "person.hire", "pay.change", "contract.sign", "grant.modify",
    "autonomy.change", "audit.delete", "audit.alter", "security.disable",
})
# What a covering grant lets the principal do, weakest first.
AUTONOMY = {"observe": DENY, "with_approval": NEEDS_APPROVAL, "act_and_notify": ALLOW, "act": ALLOW}
_RANK = list(AUTONOMY)


def grant_error(grant: Any) -> Optional[str]:
    """Why a grant is malformed, or None. Checked before a grant is stored and again when it is read."""
    if not isinstance(grant, dict):
        return "grant must be an object"
    for key in ("id", "grantor", "principal", "approver"):
        if ident(grant.get(key)) is None:
            return f"grant needs '{key}'"
    if grant["approver"] in (grant["grantor"], grant["principal"]):
        return "approver must be a person other than the grantor and the principal"
    actions = grant.get("actions")
    if not isinstance(actions, list) or not actions or any(ident(a) is None for a in actions):
        return "grant needs a non-empty list of 'actions'"
    never = [a for a in actions if any(fnmatchcase(n, a) for n in NEVER)]
    if never:
        return f"actions {never} cover something on the NEVER list"
    resources = grant.get("resources", ["*"])
    if not isinstance(resources, list) or not resources or any(ident(r) is None for r in resources):
        return "'resources' must be a non-empty list of patterns"
    if grant.get("autonomy") not in AUTONOMY:
        return f"autonomy must be one of {_RANK}"
    if grant.get("max_amount") is not None:
        limit = number(grant["max_amount"])
        if limit is None or limit <= 0 or limit > HARD_CEILING:
            return f"max_amount must be a positive number no greater than {HARD_CEILING:.0f}"
        if grant.get("currency") != CURRENCY:
            return f"a limit needs currency '{CURRENCY}'"
    start, end = number(grant.get("valid_from")), number(grant.get("valid_until"))
    if start is None or end is None or end <= start:
        return "valid_until must be after valid_from"
    if end - start > MAX_GRANT_SECONDS:
        return f"a grant may last at most {MAX_GRANT_SECONDS / 86400:.0f} days"
    return None


def _dead_reason(grant: Dict[str, Any], now: float) -> str:
    """Why a grant confers nothing at `now`; '' if it is live."""
    if grant.get("revoked_at") is not None:
        return f"grant {grant['id']} was revoked"
    if now < grant["valid_from"]:
        return f"grant {grant['id']} is not valid yet"
    if now >= grant["valid_until"]:      # valid_until itself is already outside the window
        return f"grant {grant['id']} has expired"
    return ""


def _decision(decision: str, reason: str, grant: Optional[Dict[str, Any]] = None, **extra: Any) -> Dict[str, Any]:
    return {"decision": decision, "reason": reason, "grant_id": grant["id"] if grant else None,
            "approver": grant["approver"] if grant and decision == NEEDS_APPROVAL else None,
            "notify": None, **extra}


def _to_person(reason: str, grant: Dict[str, Any]) -> Dict[str, Any]:
    return _decision(NEEDS_APPROVAL, f"{reason}; ask {grant['approver']}", grant)


def authorize(principal: Any, action: Any, resource: Any = None, context: Optional[Dict[str, Any]] = None, *,
              grants: Iterable[Dict[str, Any]] = (), now: float,
              action_types: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Decide what `principal` may do. Returns {"decision", "reason", "grant_id", "approver", "notify"}."""
    principal, action = ident(principal), ident(action)
    if principal is None or action is None:
        return _decision(DENY, "a principal and an action are required")
    resource = "*" if resource is None else ident(resource)
    if resource is None:
        return _decision(DENY, "resource must be a non-empty string when given")
    if context is not None and not isinstance(context, dict):
        return _decision(DENY, "context must be an object when given")
    context = context or {}
    types = ACTION_TYPES if action_types is None else action_types

    if action in NEVER:
        return _decision(DENY, f"'{action}' is on the NEVER list; no grant can allow it")
    if action not in types:
        return _decision(DENY, f"unknown action type '{action}'")
    monetary = bool(types[action])
    amount = number(context.get("amount"))
    if monetary:
        if amount is None or context.get("currency") is None:
            return _decision(DENY, f"'{action}' needs a numeric amount and a currency")
        if amount <= 0:
            return _decision(DENY, "amount must be positive")
        if amount > HARD_CEILING:
            return _decision(DENY, f"amount {amount:.2f} is above the hard ceiling {HARD_CEILING:.0f} {CURRENCY}; "
                                   "no grant can allow it")

    mine = sorted((g for g in grants if grant_error(g) is None and g["principal"] == principal),
                  key=lambda g: (_RANK.index(g["autonomy"]), g["id"]))
    if not mine:
        return _decision(DENY, f"no grant names {principal}")
    live = [g for g in mine if not _dead_reason(g, now)]
    if not live:
        return _decision(DENY, _dead_reason(mine[0], now), mine[0])
    covering = [g for g in live if any(fnmatchcase(action, a) for a in g["actions"])]
    if not covering:
        return _to_person(f"'{action}' is outside what {principal} was granted", live[0])
    in_scope = [g for g in covering if any(fnmatchcase(resource, r) for r in g.get("resources", ["*"]))]
    if not in_scope:
        return _to_person(f"resource '{resource}' is outside the granted resources", covering[0])

    # ponytail: with several covering grants the weakest autonomy wins (sorted above).
    # Revoke the narrower grant if the broader one should apply.
    g = in_scope[0]
    if monetary:
        if g.get("max_amount") is None:
            return _to_person(f"grant {g['id']} sets no amount limit", g)
        if context.get("currency") != CURRENCY:
            return _to_person(f"only {CURRENCY} amounts can be checked (got {context.get('currency')})", g)
        if amount > g["max_amount"]:        # type: ignore[operator]
            return _to_person(f"amount {amount:.2f} exceeds the granted limit {g['max_amount']:.2f} {CURRENCY}", g)

    decision = AUTONOMY[g["autonomy"]]
    reason = f"'{action}' is within grant {g['id']} from {g['grantor']} at autonomy '{g['autonomy']}'"
    if decision == NEEDS_APPROVAL:
        return _to_person(reason, g)
    if decision == DENY:
        return _decision(DENY, f"{reason}: {principal} may observe only", g)
    return _decision(ALLOW, reason, g, notify=g["grantor"] if g["autonomy"] == "act_and_notify" else None)


def live_grants(grants: Iterable[Dict[str, Any]], now: float) -> List[Dict[str, Any]]:
    return [g for g in grants if grant_error(g) is None and not _dead_reason(g, now)]
