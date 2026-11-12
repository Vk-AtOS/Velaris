"""ITSM_ENGINE: an IT ticket and incident store with priority, SLA clocks and an audit trail.

Priority is computed, never taken on trust from the reporter:

    score = IMPACT_WEIGHT[impact] + URGENCY_WEIGHT[urgency] + sum(HISTORY_WEIGHT[flag] for each true flag)
    P1 if score >= 900, P2 if >= 600, P3 if >= 300, else P4          (maximum 1400)

Each priority carries two targets (SLA_MINUTES): first response and resolution.
The response clock stops when the ticket is first assigned. The resolution clock
runs while the ticket is open and pauses while it is on hold; time on hold
extends the due time. States and allowed moves are in TRANSITIONS.

Every change is appended to the ticket's own history (who, when, from, to, note)
and to the hash-chained trace, so the record of a ticket cannot be quietly rewritten.
"Who" is the current caller (velaris.core.access): any authenticated person or service
may open and move tickets, nobody can do it anonymously, and a legacy `by` argument
must name that same caller.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.core.access import check_caller, current_caller, deployment_org, org_denied
from velaris.agentkit.infra_store import audit

NAME = "ITSM_ENGINE"
PRIORITY_BANDS = ((900, "P1"), (600, "P2"), (300, "P3"), (0, "P4"))
SLA_MINUTES = {"P1": (15, 240), "P2": (60, 480), "P3": (240, 1440), "P4": (480, 4320)}   # (respond, resolve)
TRANSITIONS = {
    "new": ("assigned", "cancelled"),
    "assigned": ("in_progress", "on_hold", "cancelled"),
    "in_progress": ("on_hold", "resolved", "assigned"),
    "on_hold": ("in_progress",),
    "resolved": ("closed", "in_progress"),      # resolved -> in_progress is a reopen
    "closed": (),
    "cancelled": (),
}


def _mine(tk: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """`tk` if the current caller may see it. With VELARIS_ORG set the store is this deployment's
    organisation only: an unstamped ticket, or a caller of another organisation or none, sees nothing."""
    dep = deployment_org()
    if tk is None or dep is None:
        return tk
    return tk if tk.get("org") == dep and not org_denied(current_caller()) else None


@dataclass
class Ticket:
    ticket_id: str
    category: str
    priority: str
    impact: str
    urgency: str
    config_item: str
    history_flags: Dict[str, bool]


class ITSMEngine:
    SUPPORTED_CATEGORIES = {"network", "application", "database", "security", "hardware"}
    SUPPORTED_PRIORITIES = {"low", "medium", "high", "critical"}
    SUPPORTED_IMPACT = {"minor", "moderate", "major", "critical"}
    SUPPORTED_URGENCY = {"low", "medium", "high"}

    IMPACT_WEIGHT = {"minor": 50, "moderate": 150, "major": 300, "critical": 500}
    URGENCY_WEIGHT = {"low": 50, "medium": 150, "high": 300}
    HISTORY_WEIGHT = {"repeat_incident": 200, "known_error": 150, "recent_outage": 250}

    def __init__(self) -> None:
        self.name = NAME
        self._state = JsonState(NAME, "tickets.json")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": NAME, "status": "ok", "version": "1.0.0"}

    def validate(self, t: Ticket) -> List[str]:
        if not isinstance(t, Ticket):
            return ["ticket must be a Ticket"]
        e = []
        if not is_name(t.ticket_id, 64):
            e.append("ticket_id invalid")
        if t.category not in self.SUPPORTED_CATEGORIES:
            e.append("unsupported category")
        if t.priority not in self.SUPPORTED_PRIORITIES:
            e.append("unsupported priority")
        if t.impact not in self.SUPPORTED_IMPACT:
            e.append("unsupported impact")
        if t.urgency not in self.SUPPORTED_URGENCY:
            e.append("unsupported urgency")
        if not isinstance(t.config_item, str):
            e.append("config_item must be text")
        if not isinstance(t.history_flags, dict):
            return e + ["history_flags must be an object"]
        for k, v in t.history_flags.items():
            if k not in self.HISTORY_WEIGHT:
                e.append(f"unsupported history flag {k}")
            elif not isinstance(v, bool):
                e.append(f"history flag {k} must be true or false")
        return e

    def assess(self, t: Ticket) -> Dict[str, Any]:
        """Computed priority and SLA targets for a ticket. Stores nothing."""
        err = self.validate(t)
        if err:
            return {"status": "failed", "errors": err}
        parts = {"impact": self.IMPACT_WEIGHT[t.impact], "urgency": self.URGENCY_WEIGHT[t.urgency],
                 "history": sum(self.HISTORY_WEIGHT[k] for k, v in t.history_flags.items() if v)}
        score = sum(parts.values())
        priority = next(p for floor, p in PRIORITY_BANDS if score >= floor)
        respond, resolve = SLA_MINUTES[priority]
        return ok(ticket_id=t.ticket_id, score=score, parts=parts, computed_priority=priority,
                  reported_priority=t.priority, respond_within_min=respond, resolve_within_min=resolve)

    def open_ticket(self, t: Ticket, by: Optional[str] = None, now: Optional[float] = None) -> Dict[str, Any]:
        assessed = self.assess(t)
        if assessed["status"] != "ok":
            return assessed
        if (by is not None and not is_name(by)) or (now is not None and not is_number(now, 0)):
            return invalid("'by' must name who opened the ticket and now be a timestamp")
        caller, refused = check_caller(NAME, "open_ticket", {"ticket": t.ticket_id}, claimed=by)
        if refused:
            return refused
        by = caller.id
        now = time.time() if now is None else now

        def add(data: Dict[str, Any]) -> Dict[str, Any]:
            tickets = data.setdefault("tickets", {})
            if t.ticket_id in tickets:
                return fail("duplicate", "a ticket with this id already exists")
            tickets[t.ticket_id] = {
                **asdict(t), "org": deployment_org(), "state": "new", "computed_priority": assessed["computed_priority"],
                "score": assessed["score"], "opened_at": now, "responded_at": None, "resolved_at": None,
                "hold_started": None, "held_s": 0.0,
                "respond_due": now + assessed["respond_within_min"] * 60,
                "resolve_due": now + assessed["resolve_within_min"] * 60,
                "history": [{"ts": now, "by": by, "from": None, "to": "new", "note": "opened"}]}
            return ok(ticket=tickets[t.ticket_id])
        result = self._state.update(add)
        if result["status"] == "ok":
            audit(NAME, "ticket.open", {"ticket": t.ticket_id, "by": by, "priority": assessed["computed_priority"]})
        return result

    def transition(self, ticket_id: str, to: str, by: Optional[str] = None, note: str = "",
                   now: Optional[float] = None) -> Dict[str, Any]:
        if (by is not None and not is_name(by)) or not isinstance(note, str) or (now is not None and not is_number(now, 0)):
            return invalid("'by' must name who is acting, note be text and now a timestamp")
        caller, refused = check_caller(NAME, "transition", {"ticket": str(ticket_id)[:64], "to": str(to)[:32]},
                                       claimed=by)
        if refused:
            return refused
        by = caller.id
        now = time.time() if now is None else now

        def move(data: Dict[str, Any]) -> Dict[str, Any]:
            tk = _mine(data.get("tickets", {}).get(ticket_id) if isinstance(ticket_id, str) else None)
            if tk is None:
                return fail("unknown_ticket", "no such ticket")
            if to not in TRANSITIONS.get(tk["state"], ()):
                return fail("denied", f"a ticket that is {tk['state']} cannot become {to}",
                            allowed=list(TRANSITIONS[tk["state"]]))
            if tk["state"] == "on_hold":                       # leaving hold: the pause extends the due time
                paused = max(0.0, now - tk["hold_started"])
                tk["held_s"], tk["resolve_due"], tk["hold_started"] = tk["held_s"] + paused, tk["resolve_due"] + paused, None
            if to == "on_hold":
                tk["hold_started"] = now
            if to == "assigned" and tk["responded_at"] is None:
                tk["responded_at"] = now
            tk["resolved_at"] = now if to == "resolved" else None if to == "in_progress" else tk["resolved_at"]
            tk["history"].append({"ts": now, "by": by, "from": tk["state"], "to": to, "note": note[:500]})
            tk["state"] = to
            return ok(ticket=tk)
        result = self._state.update(move)
        if result["status"] == "ok":
            audit(NAME, "ticket.transition", {"ticket": ticket_id, "by": by, "to": to})
        return result

    def sla_status(self, ticket_id: str, now: Optional[float] = None) -> Dict[str, Any]:
        """Where both clocks stand: met, running (with seconds left), paused or breached."""
        if now is not None and not is_number(now, 0):
            return invalid("now must be a timestamp")
        now = time.time() if now is None else now
        tk = self._ticket(ticket_id)
        if tk is None:
            return fail("unknown_ticket", "no such ticket")

        def clock(done_at: Optional[float], due: float, paused: bool = False) -> Dict[str, Any]:
            if done_at is not None:
                return {"state": "met" if done_at <= due else "breached", "seconds_left": None}
            if paused:
                return {"state": "paused", "seconds_left": round(due - tk["hold_started"], 3)}
            return {"state": "running" if now <= due else "breached", "seconds_left": round(due - now, 3)}
        if tk["state"] == "cancelled":
            return ok(ticket_id=ticket_id, priority=tk["computed_priority"], response={"state": "cancelled"},
                      resolution={"state": "cancelled"})
        return ok(ticket_id=ticket_id, priority=tk["computed_priority"],
                  response=clock(tk["responded_at"], tk["respond_due"]),
                  resolution=clock(tk["resolved_at"], tk["resolve_due"], paused=tk["state"] == "on_hold"))

    def _ticket(self, ticket_id: Any) -> Optional[Dict[str, Any]]:
        tk = self._state.load().get("tickets", {}).get(ticket_id) if isinstance(ticket_id, str) else None
        return _mine(tk)

    def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        tk = self._ticket(ticket_id)
        return ok(ticket=tk) if tk else fail("unknown_ticket", "no such ticket")

    def list_tickets(self, state: Optional[str] = None) -> List[Dict[str, Any]]:
        """Tickets (optionally in one state), most urgent first: priority, then earliest resolution due."""
        tickets = [t for t in self._state.load().get("tickets", {}).values() if _mine(t) is not None]
        return sorted((t for t in tickets if state is None or t["state"] == state),
                      key=lambda t: (t["computed_priority"], t["resolve_due"]))
