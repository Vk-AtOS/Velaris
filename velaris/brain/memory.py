"""The brain's situational memory: what it knows between requests, with access checks (KAN-32).

  open approvals   read from the flow store when asked (Flow.waiting); never copied
  in-flight work   the brain's own run records (goal, steps, status), per organisation
  person context   short notes about what a person is working on, per organisation and person

Rules, all in code. Every read and write is scoped to the caller's organisation (one organisation's memory is not
reachable with another's caller). A person's notes are read and written by that person or a governance admin. Notes
are plain text of at most MAX_NOTE chars, masked with guard.redact before they are stored (no secrets, no PAN or
Aadhaar, no emails), at most MAX_NOTES per person (newest kept). Pay, bank, identity and health data are never put
here: they stay in their agents behind authorize_read. Anything given to a model from here goes in as fenced data.
Runs: the newest MAX_RUNS records are kept; the trace holds the complete history.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from velaris.agentkit.state import JsonState
from velaris.core.access import GOVERNANCE_ADMINS, AccessDenied, Caller, has_role
from velaris.intel import guard, trace
from velaris.intel.flow import Flow

MAX_NOTE, MAX_NOTES, MAX_RUNS = 500, 20, 300
APPROVER_ROLES = frozenset({"flow_approver"}) | GOVERNANCE_ADMINS


def _state() -> JsonState:
    return JsonState("brain", "memory.json", {"people": {}, "runs": {}}, version=1)


def _may_see_person(caller: Caller, person: str) -> bool:
    return caller.id == person or has_role(caller, GOVERNANCE_ADMINS)


def note(caller: Caller, person: str, text: str) -> str:
    """Remember `text` about `person` (in the caller's organisation). Returns the stored (masked) text."""
    if not _may_see_person(caller, person):
        raise AccessDenied("a person's notes are for that person or a governance admin")
    if not isinstance(text, str) or not text.strip():
        raise ValueError("a note is some text")
    masked = guard.redact(text.strip()[:MAX_NOTE])[0]
    key = f"{caller.org}:{person}"

    def add(d: Dict[str, Any]) -> None:
        d["people"][key] = (d["people"].get(key, []) + [{"ts": time.time(), "by": caller.id, "text": masked}])[-MAX_NOTES:]
    _state().update(add)
    trace.append("brain", "memory.note", {"org": caller.org, "person": person, "by": caller.id, "chars": len(masked)})
    return masked


def notes(caller: Caller, person: str) -> List[Dict[str, Any]]:
    if not _may_see_person(caller, person):
        raise AccessDenied("a person's notes are for that person or a governance admin")
    return list(_state().load()["people"].get(f"{caller.org}:{person}", []))


def save_run(record: Dict[str, Any]) -> None:
    def put(d: Dict[str, Any]) -> None:
        d["runs"][record["id"]] = record
        if len(d["runs"]) > MAX_RUNS:
            for k in sorted(d["runs"], key=lambda k: d["runs"][k]["created"])[:len(d["runs"]) - MAX_RUNS]:
                del d["runs"][k]
    _state().update(put)


def get_run(caller: Caller, run_id: str) -> Optional[Dict[str, Any]]:
    """A run of the caller's organisation, and the caller's own unless they are a governance admin. Else None."""
    r = _state().load()["runs"].get(run_id)
    if not r or r["org"] != caller.org or (r["caller"] != caller.id and not has_role(caller, GOVERNANCE_ADMINS)):
        return None
    return r


def in_flight(caller: Caller) -> List[Dict[str, Any]]:
    """Unfinished brain runs the caller may see: {id, goal, status}."""
    mine = (r for r in _state().load()["runs"].values()
            if r["org"] == caller.org and r["status"] not in ("done", "refused") and
            (r["caller"] == caller.id or has_role(caller, GOVERNANCE_ADMINS)))
    return [{"id": r["id"], "goal": r["goal"][:200], "status": r["status"]} for r in sorted(mine, key=lambda r: r["created"])]


def open_approvals(caller: Caller, flow_path: Optional[str] = None) -> List[str]:
    """Run ids waiting for a decision: the caller's own, or the organisation's for an approver."""
    approver = bool(caller.roles & APPROVER_ROLES)
    return Flow([], path=flow_path).waiting(org=caller.org, owner=None if approver else caller.id, limit=50)


def context(caller: Caller, flow_path: Optional[str] = None) -> str:
    """Plain text for the planner prompt (the caller wraps it as data)."""
    lines = [f"- {n['text']}" for n in notes(caller, caller.id)[-5:]]
    work = [f"- {r['goal']} [{r['status']}]" for r in in_flight(caller)[-5:]]
    return "\n".join(["Notes about the person:"] + (lines or ["- none"]) + ["Work in flight:"] + (work or ["- none"]) +
                     [f"Approvals waiting: {len(open_approvals(caller, flow_path))}"])
