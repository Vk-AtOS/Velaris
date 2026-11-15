"""Scheduler state and rules on top of hiring_slots: interviewer profiles, bookings (no double booking), invitation drafts,
candidate self-schedule tokens, reminders, no-shows. State file `scheduler.json` under agent_dir("INTERVIEW_SCHEDULER"); every
record carries `org`. Candidate e-mail addresses are never stored here: drafts carry the placeholders {candidate_name} and
{candidate_email}, filled in by whoever sends the approved draft (the mail layer), so erasing a person removes only ids.

Fair slots: candidates at the same stage of the same requisition are offered the same slots. The first schedule token issued for
(requisition, stage) opens a round (it lasts as long as that token) and records the offered slot set, the panel and the length;
every later token in the round for the same panel and length gets that recorded set (minus slots since taken, which is the same
loss for everyone). A token that asks for a different panel or length is refused unless an hr_admin gives a reason, which is
recorded with who and when; that candidate then gets a set of their own.
"""
from __future__ import annotations

import secrets
from typing import Any, Dict, List, Optional

from velaris.agentkit import hiring_slots as sl
from velaris.agentkit.hiring_common import DAY, HiringError, application_known, audit, bad, hid, new_id, now, sha, store

AGENT = "INTERVIEW_SCHEDULER"
PLACEHOLDER_EMAIL, PLACEHOLDER_NAME = "{candidate_email}", "{candidate_name}"
REMINDERS = (("T-24h", 24 * 3600), ("T-1h", 3600))
MAX_TOKEN_DAYS = 30


def st() -> Any:
    return store(AGENT, "scheduler.json", {"interviewers": {}, "bookings": {}, "drafts": {}, "tokens": {}, "reminders_sent": {}, "rounds": {}})


def key(org: str, ident: str) -> str:
    return f"{org}|{ident}"


def panel_for(d: Dict[str, Any], org: str, ids: List[str]) -> List[Dict[str, Any]]:
    if not isinstance(ids, list) or not 1 <= len(ids) <= 6 or len(set(ids)) != len(ids):
        raise bad("interviewer_ids must be 1 to 6 distinct ids")
    out = []
    for i in ids:
        m = d["interviewers"].get(key(org, str(i)))
        if not m:
            raise HiringError("not_found", f"interviewer {str(i)[:40]} has no availability on file")
        out.append(m)
    return out


def org_bookings(d: Dict[str, Any], org: str) -> List[Dict[str, Any]]:
    return [b for b in d["bookings"].values() if b["org"] == org]


def organizer(org: str) -> Dict[str, str]:
    c = store("JOB_POSTINGS", "postings.json", {}).load().get("company", {}).get(org)
    if not c or not c.get("contact_email"):
        raise HiringError("not_configured", "JOB_POSTINGS.set_company_profile with a contact_email is needed (it is the invitation organizer)")
    return {"name": c["name"], "email": c["contact_email"]}


def make_ics(b: Dict[str, Any], method: str, panel: List[Dict[str, Any]], org: str, at: float) -> str:
    org_ = organizer(org)
    people = [(m["name"], m["email"], "REQ-PARTICIPANT") for m in panel] + [("Candidate", PLACEHOLDER_EMAIL, "REQ-PARTICIPANT")]
    return sl.build_ics(method, uid=b["uid"], sequence=b["sequence"], start=b["start"], end=b["end"], stamp=at,
                        summary=b["title"], description=b["notes"] or "Interview", location=b["location"],
                        organizer=(org_["name"], org_["email"]), attendees=people)


def draft(d: Dict[str, Any], b: Dict[str, Any], kind: str, panel: List[Dict[str, Any]], by: str, at: float) -> Dict[str, Any]:
    """An invitation e-mail as a DRAFT (nothing is sent; a person approves, the mail layer sends)."""
    when = sl.datetime.fromtimestamp(b["start"], sl.IST).strftime("%A %d %B %Y, %H:%M IST")
    method = "CANCEL" if kind == "cancel" else "REQUEST"
    verb = {"invite": "You are invited to", "reschedule": "Your interview has moved. New time for", "cancel": "Cancelled:",
            "no_show_followup": "We missed you. Pick a new time for", "reminder": "Reminder:"}[kind]
    body = (f"Hello {PLACEHOLDER_NAME},\n\n{verb} {b['title']}\nWhen: {when} ({b['duration_min']} minutes)\nWhere: {b['location']}\n"
            + ("\nTo pick another time or cancel: {schedule_link}\n" if kind != "cancel" else "") + "\nThank you.")
    dr = {"id": new_id("draft"), "org": b["org"], "booking_id": b["id"], "kind": kind, "status": "draft", "created_by": by, "created_at": at,
          "to": {"candidate_id": b["candidate_id"], "interviewer_emails": [m["email"] for m in panel]},
          "subject": f"{'Cancelled: ' if kind == 'cancel' else ''}{b['title']} on {when}", "body": body,
          "ics": make_ics(b, method, panel, b["org"], at) if kind in ("invite", "reschedule", "cancel") else None,
          "placeholders": [PLACEHOLDER_NAME, PLACEHOLDER_EMAIL, "{schedule_link}"], "sent": False}
    d["drafts"][dr["id"]] = dr
    return dr


def offered_set(d: Dict[str, Any], app: Dict[str, Any], ids: List[str], duration_min: int, days: int, at: float,
                reason: str, admin: bool, by: str) -> Dict[str, Any]:
    """The slot starts this token may offer, under the fair-slot rule (see the module docstring)."""
    org, panel = app["org"], sorted(ids)
    key = f"{org}|{app['requisition_id']}|{app['stage']}"
    rnd = d["rounds"].get(key)
    if rnd and rnd["expires"] > at and (rnd["panel"] != panel or rnd["duration_min"] != duration_min):
        if not reason.strip():
            raise HiringError("conflict", "other candidates at this stage of this requisition were offered different slots (another panel or length); "
                                          "an hr_admin may issue this one with divergence_reason")
        if not admin:
            raise HiringError("denied", "only an hr_admin may give a different slot set than the round's, and only with a recorded reason")
        starts = [s["start"] for s in sl.propose_slots(panel_for(d, org, ids), org_bookings(d, org), duration_min, at, at + 14 * DAY, at, limit=30)]
        rnd["exceptions"].append({"application_id": app["id"], "panel": panel, "duration_min": duration_min, "reason": reason.strip()[:300],
                                  "by": by, "at": at})
        return {"round": key, "starts": starts, "exception": True}
    if reason.strip():
        raise bad("divergence_reason is only for a token that differs from its round")
    if not rnd or rnd["expires"] <= at:
        starts = [s["start"] for s in sl.propose_slots(panel_for(d, org, ids), org_bookings(d, org), duration_min, at, at + 14 * DAY, at, limit=30)]
        rnd = d["rounds"][key] = {"org": org, "requisition_id": app["requisition_id"], "stage": app["stage"], "panel": panel,
                                  "duration_min": duration_min, "starts": starts, "opened_at": at, "expires": at + days * DAY,
                                  "opened_by": by, "exceptions": []}
    return {"round": key, "starts": list(rnd["starts"]), "exception": False}


def issue_token(d: Dict[str, Any], app: Dict[str, Any], ids: List[str], duration_min: int, days: int, title: str, location: str,
                at: float, by: str, reason: str = "", admin: bool = False) -> str:
    org = app["org"]
    if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_TOKEN_DAYS:
        raise bad(f"days must be 1 to {MAX_TOKEN_DAYS}")
    offer = offered_set(d, app, ids, duration_min, days, at, reason, admin, by)
    raw = secrets.token_urlsafe(24)
    d["tokens"][sha(raw)] = {"org": org, "application_id": app["id"], "candidate_id": app["candidate_id"], "interviewers": ids,
                             "duration_min": duration_min, "title": title, "location": location, "expires": at + days * DAY,
                             "booking_id": None, "round": offer["round"], "starts": offer["starts"]}
    return raw


def reminder_list(d: Dict[str, Any], org: str, at: float, within_h: float) -> List[Dict[str, Any]]:
    out = []
    for b in org_bookings(d, org):
        if b["status"] != "confirmed" or b["start"] <= at:
            continue
        for label, lead in REMINDERS:
            due = b["start"] - lead
            sent = f"{b['id']}|{b['sequence']}|{label}" in d["reminders_sent"]
            if not sent and due <= at + within_h * 3600:
                out.append({"booking_id": b["id"], "kind": label, "due_at": due, "overdue": due < at, "candidate_id": b["candidate_id"],
                            "interviewers": b["interviewers"], "start_ist": sl.datetime.fromtimestamp(b["start"], sl.IST).strftime("%a %d %b %H:%M")})
    return sorted(out, key=lambda r: r["due_at"])


def export_candidate(org: str, candidate_id: str) -> Dict[str, Any]:
    d = st().load()
    return {"interview_bookings": [b for b in org_bookings(d, org) if b["candidate_id"] == candidate_id]}


def purge_candidate(org: str, candidate_id: str) -> int:
    """Drafts and tokens go; bookings stay as anonymous capacity history (who/when of the interviewers, no candidate)."""
    def go(d: Dict[str, Any]) -> int:
        n = 0
        for k in [k for k, x in d["drafts"].items() if x["org"] == org and x["to"]["candidate_id"] == candidate_id]:
            del d["drafts"][k]
            n += 1
        for k in [k for k, t in d["tokens"].items() if t["org"] == org and t["candidate_id"] == candidate_id]:
            del d["tokens"][k]
            n += 1
        for b in d["bookings"].values():
            if b["org"] == org and b["candidate_id"] == candidate_id:
                b.update(candidate_id=None, application_id=None, notes="")
                n += 1
        return n
    return st().update(go)


def create_booking(d: Dict[str, Any], org: str, by: str, application_id: str, ids: List[str], start: float, duration_min: int,
                   title: str, location: str, notes: str, at: float, *, replace: Optional[str] = None) -> Dict[str, Any]:
    """Book (or move, with replace=<booking id>) a slot inside an open state update. Re-checks the slot against every current
    booking of every panel member, so two requests for the same time cannot both succeed."""
    app = application_known(org, application_id)
    if not app or not app.get("candidate_id"):
        raise HiringError("not_found", "no such application")
    panel = panel_for(d, org, ids)
    if not sl.slot_is_free(panel, org_bookings(d, org), start, duration_min, at, ignore_booking=replace):
        raise HiringError("conflict", "that time is not free for every interviewer (hours, buffers, daily maximum, time off or another booking)")
    if replace:
        b = d["bookings"][replace]
        b.update(start=start, end=start + duration_min * 60, duration_min=duration_min, sequence=b["sequence"] + 1, status="confirmed")
        kind = "reschedule"
    else:
        bid = new_id("bk")
        b = {"id": bid, "org": org, "uid": f"{bid}@velaris.local", "sequence": 0, "application_id": application_id,
             "candidate_id": app["candidate_id"], "interviewers": list(ids), "start": start, "end": start + duration_min * 60,
             "duration_min": duration_min, "title": str(title)[:160] or "Interview", "location": str(location)[:200], "notes": str(notes)[:500],
             "status": "confirmed", "created_by": by, "created_at": at, "history": []}
        d["bookings"][bid] = b
        kind = "invite"
    b["history"].append({"at": at, "by": by, "event": kind, "start": start})
    dr = draft(d, b, kind, panel, by, at)
    return {"booking": b, "draft_id": dr["id"]}


def _token(d: Dict[str, Any], raw: Any, at: float) -> Optional[Dict[str, Any]]:
    t = d["tokens"].get(sha(raw)) if isinstance(raw, str) and 20 <= len(raw) <= 80 else None
    return t if t and t["expires"] > at else None


def revoke_tokens(org: str, application_ids: List[str]) -> int:
    """Remove every self-scheduling link of these applications (a withdrawal: the candidate must not be able to book again)."""
    def go(d: Dict[str, Any]) -> int:
        gone = [h for h, t in d["tokens"].items() if t["org"] == org and t["application_id"] in application_ids]
        for h in gone:
            del d["tokens"][h]
        return len(gone)
    return st().update(go)


def public_slots(token: str) -> Dict[str, Any]:
    """Candidate side (no login): the slots recorded for this token's round that are still free. Same set for every candidate of the stage."""
    at, d = now(), st().load()
    t = _token(d, token, at)
    if not t:
        return {"status": "not_found", "reason": "this link is not valid or has expired"}
    try:
        free = sl.propose_slots(panel_for(d, t["org"], t["interviewers"]), org_bookings(d, t["org"]), t["duration_min"], at,
                                at + 14 * DAY, at, limit=1000)
    except HiringError as e:
        return {"status": e.status, "reason": e.reason}
    offered = set(t["starts"])
    slots = [s for s in free if s["start"] in offered]       # the recorded set, minus what has been taken since
    return {"status": "ok", "title": t["title"], "duration_min": t["duration_min"], "slots": [s["start_ist"] + " IST" for s in slots],
            "starts": [s["start"] for s in slots]}


def public_pick(token: str, start: float) -> Dict[str, Any]:
    """Candidate side: take a slot (or move the earlier pick). The invitation stays a draft until a person approves it."""
    at = now()
    try:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            t = _token(d, token, at)
            if not t:
                raise HiringError("not_found", "this link is not valid or has expired")
            if isinstance(start, bool) or not isinstance(start, (int, float)):
                raise bad("start must be one of the offered starts")
            if not any(abs(start - x) < 1 for x in t["starts"]):
                raise HiringError("conflict", "that time was not offered on this link")
            out = create_booking(d, t["org"], "candidate-token", t["application_id"], t["interviewers"], float(start), t["duration_min"],
                                 t["title"], t["location"], "", at, replace=t["booking_id"])
            t["booking_id"] = out["booking"]["id"]
            audit(AGENT, "booking.self_scheduled", t["org"], None, booking=hid(t["org"], t["booking_id"]), sequence=out["booking"]["sequence"])
            return {"status": "ok", "confirmed_for": sl.datetime.fromtimestamp(out["booking"]["start"], sl.IST).strftime("%A %d %B %Y, %H:%M IST")}
        return st().update(go)
    except HiringError as e:
        return {"status": e.status, "reason": e.reason}


def public_cancel(token: str) -> Dict[str, Any]:
    at = now()
    try:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            t = _token(d, token, at)
            if not t or not t["booking_id"] or d["bookings"][t["booking_id"]]["status"] != "confirmed":
                raise HiringError("not_found", "nothing to cancel on this link")
            b = d["bookings"][t["booking_id"]]
            b.update(status="cancelled", sequence=b["sequence"] + 1)
            b["history"].append({"at": at, "by": "candidate-token", "event": "cancel"})
            draft(d, b, "cancel", panel_for(d, t["org"], t["interviewers"]), "candidate-token", at)
            audit(AGENT, "booking.cancelled", t["org"], None, booking=hid(t["org"], b["id"]), by_candidate=True)
            t["booking_id"] = None
            return {"status": "ok"}
        return st().update(go)
    except HiringError as e:
        return {"status": e.status, "reason": e.reason}
