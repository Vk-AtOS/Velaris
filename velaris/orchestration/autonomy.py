"""Autonomy policy: which action classes run alone and which need a human (KAN-33).

One table, action class -> mode:

  auto         the tool runs
  auto_notify  the tool runs and a "notify" entry goes to the trace (people read it there)
  approval     the run stops until a person (or Prime) approves THIS exact call
  forbidden    the tool does not run; the model is told so

A tool's class is worked out by code from its ToolSpec and, for money, its arguments; a model never sets it.
When several classes could apply the STRICTEST wins, and an act method nobody classified is "unclassified"
(approval). The shipped table is conservative: everything irreversible, money, personal-data export, external
message, access change, deployment and legal filing needs a human.

The owner edits the table (`set_mode`, governance admin only, traced). Classes in LOCKED refuse `auto` and
`auto_notify` in an edit: loosening those is a decision made in code, not in a dashboard. The table is
stored in <VELARIS_DATA>/agents/orchestration/autonomy.json; a damaged file means the defaults.

`permit(tool, args)` has the signature of Flow's `permit=`. `to_aae_rules()` exports the same table as AAE_POLICY
rules ({"type": <class>} actions), so the two never disagree.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from velaris.agentkit.state import JsonState
from velaris.core.access import GOVERNANCE_ADMINS, check_caller
from velaris.intel import tools, trace

logger = logging.getLogger("velaris.orchestration.autonomy")

# Strictest last: when several classes fit, the one with the highest index wins.
CLASSES = ("read", "personal_data_read", "internal_write", "unclassified", "money_under_limit", "external_message",
           "access_change", "personal_data_export", "irreversible", "deployment", "legal_filing", "money_over_limit")
MODES = ("auto", "auto_notify", "approval", "forbidden")
DEFAULT_MODES: Dict[str, str] = {
    "read": "auto", "personal_data_read": "auto_notify", "internal_write": "auto_notify", "unclassified": "approval",
    "money_under_limit": "approval", "money_over_limit": "approval", "external_message": "approval",
    "personal_data_export": "approval", "access_change": "approval", "irreversible": "approval",
    "deployment": "approval", "legal_filing": "approval"}
LOCKED = frozenset({"money_over_limit", "external_message", "personal_data_export", "access_change", "irreversible",
                    "deployment", "legal_filing"})
ADMIN = ("governance_admin",)
APPROVER_ROLES: Dict[str, Tuple[str, ...]] = {          # who may approve a call of this class (local decisions)
    "money_under_limit": ("payroll_admin",) + ADMIN, "money_over_limit": ("payroll_admin",) + ADMIN,
    "personal_data_export": ("hr_admin",) + ADMIN, "access_change": ("security_admin",) + ADMIN,
    "deployment": ("infra_admin",) + ADMIN, "legal_filing": ADMIN, "irreversible": ("hr_admin", "flow_approver") + ADMIN}
DEFAULT_APPROVERS = ("flow_approver",) + ADMIN
MAX_MONEY_LIMIT = 5_000_000.0           # the AetherOS Prime hard ceiling (aether_os/prime/authz.py)

# Reviewed exceptions: act methods that only change the caller's own or internal reversible state.
INTERNAL_WRITES = frozenset({"LEAVE_MANAGEMENT.apply", "ITSM_ENGINE.transition", "LONGTERM_MEMORY.remember",
                             "POLICY_ACKS.acknowledge", "ONBOARDING_FLOW.complete_task"})
_WORDS = {
    "irreversible": ("delete", "erase", "purge", "void", "finalis", "finaliz", "seal", "discard"),
    "access_change": ("grant", "revoke", "role", "permission", "token", "availability"),
    "deployment": ("deploy", "rollout", "release"),
    "legal_filing": ("filing", "efil"),
    "personal_data_export": ("export",),
}
_MONEY_WORDS = ("pay", "transfer", "refund", "disburse", "invoice")     # matched as the start of a word of the method name
_MONEY_PARAMS = ("amount", "amount_inr", "payment")


def _state() -> JsonState:
    return JsonState("orchestration", "autonomy.json", {"modes": {}, "money_limit": 0.0}, version=1)


def table() -> Dict[str, Any]:
    """The effective table: {"modes": {class: mode}, "money_limit": float}. Unknown or invalid stored values are ignored."""
    try:
        stored = _state().load()
    except (ValueError, OSError) as e:      # unreadable: the conservative defaults (and say so)
        logger.warning("autonomy table unreadable, using defaults: %s", type(e).__name__)
        stored = {}
    modes = dict(DEFAULT_MODES)
    for cls, mode in (stored.get("modes") or {}).items():
        if cls in DEFAULT_MODES and mode in MODES and not (cls in LOCKED and mode in ("auto", "auto_notify")):
            modes[cls] = mode
    limit = stored.get("money_limit")
    limit = float(limit) if isinstance(limit, (int, float)) and not isinstance(limit, bool) and 0 <= limit <= MAX_MONEY_LIMIT else 0.0
    return {"modes": modes, "money_limit": limit}


def classify(spec: tools.ToolSpec, args: Optional[Dict[str, Any]] = None, *, limit: Optional[float] = None) -> str:
    """The action class of one call. Strictest of every class that fits; read only for a method that cannot change anything."""
    name, method = spec.name, spec.method.lower()
    tokens = method.split("_")
    has = lambda words: any(t.startswith(w) for t in tokens for w in words)       # noqa: E731
    found: List[str] = []
    for cls, words in _WORDS.items():
        if has(words):
            found.append(cls)
    if "file" in tokens and has(("return", "gst", "tds", "tax")) and "legal_filing" not in found:
        found.append("legal_filing")                                              # file_gst_return, but not file_note
    if spec.side_effects == "none":
        found.append("personal_data_read" if spec.sensitivity == "restricted" else "read")
        found = [c for c in found if c != "irreversible"]       # a read named "..._seal_..." deletes nothing
    else:
        if spec.side_effects == "external":
            found.append("external_message")
        if name in INTERNAL_WRITES:
            found.append("internal_write")
        elif not found:
            found.append("unclassified")
    props = (spec.params.get("properties") or {})
    if spec.side_effects != "none" and (has(_MONEY_WORDS) or any(p in props for p in _MONEY_PARAMS)):
        amount = next((args.get(p) for p in _MONEY_PARAMS if isinstance(args, dict) and p in args), None)
        cap = table()["money_limit"] if limit is None else limit
        ok = isinstance(amount, (int, float)) and not isinstance(amount, bool) and 0 <= amount <= cap
        found.append("money_under_limit" if ok else "money_over_limit")
    return max(found, key=CLASSES.index)


def mode_of(cls: str) -> str:
    return table()["modes"].get(cls, "approval")


def approver_roles(cls: str) -> Tuple[str, ...]:
    return APPROVER_ROLES.get(cls, DEFAULT_APPROVERS)


def permit(tool: str, args: Dict[str, Any]) -> str:
    """Flow's permit=: allow | approve | deny. A tool the registry does not know needs approval."""
    spec = tools.get(tool)
    if spec is None:
        return "approve"
    cls = classify(spec, args)
    mode = mode_of(cls)
    if mode == "auto_notify":
        trace.append("autonomy", "notify", {"tool": tool, "class": cls, "args": sorted(args)[:20]})
    return {"auto": "allow", "auto_notify": "allow", "forbidden": "deny"}.get(mode, "approve")


def set_mode(cls: str, mode: str, *, by: str = "") -> None:
    """Change one class's mode. Governance admin only (the acting caller); LOCKED classes refuse auto modes."""
    if cls not in CLASSES or mode not in MODES:
        raise ValueError(f"class is one of {CLASSES}, mode one of {MODES}")
    if cls in LOCKED and mode in ("auto", "auto_notify"):
        raise ValueError(f"'{cls}' always needs a human; it cannot be set to {mode}")
    who, refused = check_caller("AUTONOMY", "set_mode", {"class": cls, "mode": mode}, roles=GOVERNANCE_ADMINS)
    if refused:
        raise PermissionError(refused["reason"])
    _state().update(lambda d: d.setdefault("modes", {}).__setitem__(cls, mode))
    trace.append("autonomy", "mode.set", {"class": cls, "mode": mode, "by": who.id if who else by})


def set_money_limit(amount: float, *, by: str = "") -> None:
    """The most a money action may be for `money_under_limit` to apply. 0 (the default) means every amount needs approval."""
    if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not 0 <= amount <= MAX_MONEY_LIMIT:
        raise ValueError(f"the limit is a number from 0 to {MAX_MONEY_LIMIT:.0f}")
    who, refused = check_caller("AUTONOMY", "set_money_limit", {"amount": amount}, roles=GOVERNANCE_ADMINS)
    if refused:
        raise PermissionError(refused["reason"])
    _state().update(lambda d: d.__setitem__("money_limit", float(amount)))
    trace.append("autonomy", "money_limit.set", {"amount": amount, "by": who.id if who else by})


def to_aae_rules() -> List[Dict[str, Any]]:
    """The table as AAE_POLICY rules for actions {"type": <class>}; a class with no rule is denied there."""
    effect = {"auto": "allow", "auto_notify": "allow", "approval": "require_approval", "forbidden": "deny"}
    return [{"id": f"autonomy.{c}", "effect": effect[m], "if": [{"field": "type", "op": "==", "value": c}]}
            for c, m in table()["modes"].items()]
