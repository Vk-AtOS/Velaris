"""Executive absence: delegated authority, bounded and time-limited, fully traced (KAN-34).

A person (the principal) records a delegation for a window: which department(s), which action classes, how much
money. While it is active the orchestrator may approve, in the principal's name, a step that would otherwise wait
for them AND falls inside the delegation. Everything else keeps waiting and is listed for the return briefing.

Bounds, all in code (these mirror AetherOS Prime's hard maxima, aether_os/prime/authz.py):
  * a window is at most MAX_DAYS (90) long and must end in the future;
  * the money limit is at most MAX_AMOUNT (5,000,000);
  * only DELEGABLE classes can be delegated: never irreversible, external message, personal-data export, access
    change, deployment or legal filing, whatever the principal writes;
  * only a person who could approve that class themselves (their roles, as recorded when the delegation was made,
    meet autonomy.approver_roles) is covered; a person's own request is never approved by their delegation;
  * the principal makes their own delegation; the principal or a governance admin revokes it, at any time, and a
    revoked or expired delegation is refused at the moment of use.

Every grant, use, queueing and revocation is one row of an append-only ledger (also written to the trace). With an
approval gate (Prime) configured the orchestrator never approves locally: it only queues, and the briefing says so.
`briefing()` is what the principal reads on return: decided under their delegation, still waiting, and escalated.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from velaris.agentkit.state import JsonState, append_line, read_lines
from velaris.agents import department_dirs
from velaris.core.access import GOVERNANCE_ADMINS, Caller, has_role
from velaris.intel import trace
from velaris.intel.paths import agent_dir
from velaris.orchestration import autonomy

MAX_DAYS = 90
MAX_AMOUNT = 5_000_000.0
DELEGABLE = frozenset({"money_under_limit", "internal_write", "unclassified"})
MAX_ACTIVE_PER_PRINCIPAL = 20
Clock = Callable[[], float]


class AbsenceError(ValueError):
    """The delegation is not allowed (the message says why and is safe to show)."""


def _store() -> JsonState:
    return JsonState("orchestration", "delegations.json", {"items": {}}, version=1)


def _ledger_path() -> Any:
    return agent_dir("orchestration") / "absence_ledger.jsonl"


def _log(row: Dict[str, Any], now: float) -> None:
    row = {"ts": now, **row}
    append_line(_ledger_path(), row)            # raises if it cannot be written: no unrecorded use of authority
    trace.append("absence", row["event"], {k: v for k, v in row.items() if k not in ("event", "ts")})


def grant(caller: Caller, *, classes: List[str], departments: List[str], start: float, end: float,
          max_amount: float = 0.0, note: str = "", clock: Clock = time.time) -> Dict[str, Any]:
    now = clock()
    known = {d.name for d in department_dirs()}
    if not classes or not set(classes) <= DELEGABLE:
        raise AbsenceError(f"classes must be a non-empty subset of {sorted(DELEGABLE)}")
    if not departments or not set(departments) <= known:
        raise AbsenceError("departments must be a non-empty list of existing departments")
    if not all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in (start, end, max_amount)):
        raise AbsenceError("start, end and max_amount must be numbers")
    if not (0 <= max_amount <= MAX_AMOUNT):
        raise AbsenceError(f"max_amount is from 0 to {MAX_AMOUNT:.0f}")
    if not (end > start and end > now) or end - start > MAX_DAYS * 86400:
        raise AbsenceError(f"the window must end after it starts and in the future, and last at most {MAX_DAYS} days")
    item = {"id": uuid.uuid4().hex[:16], "principal": caller.id, "org": caller.org, "roles": sorted(caller.roles),
            "classes": sorted(set(classes)), "departments": sorted(set(departments)), "max_amount": float(max_amount),
            "start": float(start), "end": float(end), "note": str(note)[:300], "created_at": now,
            "revoked_at": None, "revoked_by": None}

    def add(d: Dict[str, Any]) -> None:
        mine = [i for i in d["items"].values() if i["principal"] == caller.id and not i["revoked_at"] and i["end"] > now]
        if len(mine) >= MAX_ACTIVE_PER_PRINCIPAL:
            raise AbsenceError("too many active delegations; revoke one first")
        d["items"][item["id"]] = item
    _store().update(add)
    _log({"event": "granted", "delegation": item["id"], "principal": caller.id, "org": caller.org,
          "classes": item["classes"], "departments": item["departments"], "max_amount": item["max_amount"],
          "start": item["start"], "end": item["end"]}, now)
    return item


def get(delegation_id: str) -> Optional[Dict[str, Any]]:
    return _store().load()["items"].get(delegation_id)


def revoke(caller: Caller, delegation_id: str, *, clock: Clock = time.time) -> bool:
    """The principal, or a governance admin of the same organisation. Returns False for an unknown or already revoked one."""
    now = clock()

    def go(d: Dict[str, Any]) -> bool:
        i = d["items"].get(delegation_id)
        if not i or i["revoked_at"] or i["org"] != caller.org:
            return False
        if i["principal"] != caller.id and not has_role(caller, GOVERNANCE_ADMINS):
            raise PermissionError("only the principal or a governance admin may revoke a delegation")
        i["revoked_at"], i["revoked_by"] = now, caller.id
        return True
    done = _store().update(go)
    if done:
        _log({"event": "revoked", "delegation": delegation_id, "by": caller.id, "org": caller.org}, now)
    return bool(done)


def active(org: str, now: float) -> List[Dict[str, Any]]:
    return [i for i in _store().load()["items"].values()
            if i["org"] == org and not i["revoked_at"] and i["start"] <= now < i["end"]]


def _covers(i: Dict[str, Any], department: str, cls: str, args: Dict[str, Any]) -> Optional[str]:
    """None when the delegation covers this call, else the reason it does not."""
    if department not in i["departments"]:
        return "department_not_covered"
    if cls not in DELEGABLE or cls not in i["classes"]:
        return "class_not_delegable" if cls not in DELEGABLE else "class_not_covered"
    if not set(i["roles"]) & set(autonomy.approver_roles(cls)):
        return "principal_could_not_approve_this_themselves"
    if cls == "money_under_limit":
        amount = next((args.get(p) for p in autonomy._MONEY_PARAMS if p in args), None)
        if not (isinstance(amount, (int, float)) and not isinstance(amount, bool) and 0 <= amount <= i["max_amount"]):
            return "over_the_delegated_amount"
    return None


def consider(*, org: str, owner: str, department: str, tool: str, cls: str, args: Dict[str, Any], run_id: str,
             call_hash: str, may_decide: bool = True, clock: Clock = time.time) -> Optional[Dict[str, Any]]:
    """A step is waiting for approval. Returns the delegation that covers it (and the caller then records the decision
    as `by=delegate_name(...)`), or None: then the step waits and is written to the ledger once as queued.

    `may_decide` False (an approval gate is configured) never returns a delegation: the step is only queued."""
    now = clock()
    mine = [i for i in active(org, now) if department in i["departments"] and i["principal"] != owner]
    reasons: List[Tuple[Dict[str, Any], str]] = []
    for i in mine:
        why = _covers(i, department, cls, args)
        if why is None and may_decide:
            _log({"event": "decided", "delegation": i["id"], "principal": i["principal"], "org": org, "run_id": run_id,
                  "call_hash": call_hash, "tool": tool, "class": cls, "department": department}, now)
            return i
        reasons.append((i, why or "approval_gate_decides"))
    seen = {(r.get("delegation"), r.get("run_id"), r.get("call_hash")) for r in read_lines(_ledger_path())
            if r.get("event") == "queued"}
    for i, why in reasons:
        if (i["id"], run_id, call_hash) not in seen:
            _log({"event": "queued", "delegation": i["id"], "principal": i["principal"], "org": org, "run_id": run_id,
                  "call_hash": call_hash, "tool": tool, "class": cls, "department": department, "why": why}, now)
    return None


def escalated(*, org: str, department: str, run_id: str, reason: str, clock: Clock = time.time) -> None:
    """A run of this department ended without an answer while a delegation covered it: tell the briefing."""
    now = clock()
    for i in active(org, now):
        if department in i["departments"]:
            _log({"event": "escalated", "delegation": i["id"], "principal": i["principal"], "org": org,
                  "run_id": run_id, "department": department, "why": reason}, now)


def delegate_name(delegation: Dict[str, Any]) -> str:
    return f"delegate:{delegation['principal']}:{delegation['id']}"


def briefing(caller: Caller, *, since: float = 0.0, still_waiting: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """What happened under `caller`'s delegations since `since`: decided, waiting (queued) and escalated, and the delegations.
    `still_waiting` (run ids, e.g. Flow.waiting()) drops queued steps somebody has meanwhile decided."""
    mine = {i["id"]: i for i in _store().load()["items"].values() if i["principal"] == caller.id and i["org"] == caller.org}
    rows = [r for r in read_lines(_ledger_path()) if r.get("delegation") in mine and r["ts"] >= since]
    by = lambda ev: [{k: v for k, v in r.items() if k != "event"} for r in rows if r["event"] == ev]      # noqa: E731
    queued = by("queued")
    if still_waiting is not None:
        live = set(still_waiting)
        queued = [q for q in queued if q["run_id"] in live]
    decided_keys = {(r["run_id"], r["call_hash"]) for r in by("decided")}
    return {"principal": caller.id, "since": since,
            "delegations": [{k: i[k] for k in ("id", "classes", "departments", "max_amount", "start", "end", "revoked_at")}
                            for i in mine.values()],
            "decided": by("decided"), "queued": [q for q in queued if (q["run_id"], q["call_hash"]) not in decided_keys],
            "escalated": by("escalated"), "revoked": by("revoked")}
