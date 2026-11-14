"""INTERVIEW_SCHEDULER: who can interview when, bookings, invitations as drafts, self-scheduling, reminders, no-shows.

The slot algorithm and iCalendar builder are in velaris.agentkit.hiring_slots (stdlib, tested against hand-computed cases);
state and booking rules are in velaris.agentkit.hiring_sched. Invitations are DRAFTS: approve_draft marks one approved; hand_off_to_mail then
puts it in a mailbox as a mail DRAFT (config["sender"], velaris.agentkit.hr_wiring.MailDraftSender) for a person to read and send.
This agent never sends anything. The candidate side (public_slots, public_pick, public_cancel in
velaris.agentkit.hiring_sched) works from a hashed, expiring token and is not exposed in the identity-authenticated API.
A no-show is recorded and a follow-up drafted; it never rejects or withdraws anyone.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_sched as hs
from velaris.agentkit import hiring_slots as sl
from velaris.agentkit.hiring_common import HIRING, PANEL, RECRUITING, HiringError, acts, audit, bad, hid, mine, now, reads
from velaris.agentkit.results import ok
from velaris.agents.ATS_CORE.main import AtsCore

logger = logging.getLogger("INTERVIEW_SCHEDULER")
AGENT = hs.AGENT


def _ts(value: Any, name: str) -> float:
    """An ISO datetime; with no offset it is Asia/Kolkata local time."""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as e:
        raise bad(f"{name} must be an ISO date-time like 2027-03-01T10:00+05:30") from e
    return (dt if dt.tzinfo else dt.replace(tzinfo=sl.IST)).timestamp()


def _booking(d: Dict[str, Any], org: str, bid: Any) -> Dict[str, Any]:
    b = d["bookings"].get(str(bid))
    if not b or b["org"] != org:
        raise HiringError("not_found", "no such booking")
    return b


class InterviewScheduler:
    """Slots, bookings, iCalendar invitations (as drafts), self-schedule tokens, reminders, no-shows."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}

    def health_check(self) -> Dict[str, Any]:
        return {"agent": AGENT, "status": "ok", "timezone": "Asia/Kolkata"}

    @acts(AGENT, PANEL)
    def set_availability(self, caller, interviewer_id: str, name: str, email: str, weekly: Dict[str, Any], buffer_min: int = 10,
                         max_per_day: int = 4, time_off: Optional[List[List[str]]] = None) -> Dict[str, Any]:
        """An interviewer's weekly hours (IST), buffer, daily maximum and time off [[start, end], ...]. Own record, or a recruiter's."""
        if interviewer_id != caller.id and not caller.roles & RECRUITING:
            raise HiringError("denied", "an interviewer sets their own availability (a recruiter may set anyone's)")
        for v, n, hi in ((buffer_min, "buffer_min", 120), (max_per_day, "max_per_day", 12)):
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= hi:
                raise bad(f"{n} must be 0 to {hi}")
        if not isinstance(email, str) or "@" not in email or len(email) > 254:
            raise bad("email is required (it goes on the calendar invitation)")
        off = []
        for pair in time_off or []:
            if not isinstance(pair, list) or len(pair) != 2:
                raise bad("time_off is a list of [start, end]")
            a, b = _ts(pair[0], "time_off start"), _ts(pair[1], "time_off end")
            if b <= a:
                raise bad("a time_off range must end after it starts")
            off.append([a, b])
        rec = {"id": hc.need_text(interviewer_id, "interviewer_id", 80), "org": caller.org, "name": hc.need_text(name, "name", 120), "email": email.strip(),
               "weekly": sl.parse_weekly(weekly), "buffer_min": buffer_min, "max_per_day": max_per_day, "time_off": off}

        def go(d: Dict[str, Any]) -> None:
            audit(AGENT, "availability.set", caller.org, caller, interviewer=hid(caller.org, interviewer_id))
            d["interviewers"][hs.key(caller.org, interviewer_id)] = rec
        hs.st().update(go)
        return ok(interviewer=rec)

    @reads(AGENT, PANEL)
    def list_interviewers(self, caller) -> Dict[str, Any]:
        return ok(interviewers=[{k: m[k] for k in ("id", "name", "weekly", "buffer_min", "max_per_day")} for m in mine(hs.st().load()["interviewers"].values(), caller.org)])

    @reads(AGENT, HIRING)
    def propose_slots(self, caller, interviewer_ids: List[str], duration_min: int, from_date: str, to_date: str, step_min: int = 30,
                      notice_hours: float = 4) -> Dict[str, Any]:
        """Free slots (UTC epoch plus IST text) where every listed interviewer is free."""
        d = hs.st().load()
        slots = sl.propose_slots(hs.panel_for(d, caller.org, interviewer_ids), hs.org_bookings(d, caller.org), duration_min,
                                 _ts(from_date, "from_date"), _ts(to_date, "to_date"), now(), step_min, notice_hours)
        return ok(slots=slots, timezone="Asia/Kolkata")

    @acts(AGENT, RECRUITING)
    def book_interview(self, caller, application_id: str, interviewer_ids: List[str], start: str, duration_min: int, title: str,
                       location: str = "", notes: str = "") -> Dict[str, Any]:
        """Book a free slot (re-checked against every current booking: no double booking) and draft the invitation."""
        at = now()
        s = _ts(start, "start")

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            out = hs.create_booking(d, caller.org, caller.id, application_id, interviewer_ids, s, duration_min, title, location, notes, at)
            audit(AGENT, "booking.created", caller.org, caller, booking=hid(caller.org, out["booking"]["id"]), application=hid(caller.org, application_id))
            return out
        out = hs.st().update(go)
        return ok(booking=out["booking"], invitation_draft_id=out["draft_id"], sent=False)

    @acts(AGENT, RECRUITING)
    def reschedule_interview(self, caller, booking_id: str, new_start: str) -> Dict[str, Any]:
        """Move a booking: same UID, SEQUENCE + 1, a REQUEST draft."""
        at, s = now(), _ts(new_start, "new_start")

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            b = _booking(d, caller.org, booking_id)
            if b["status"] not in ("confirmed", "no_show_candidate", "no_show_interviewer"):
                raise HiringError("conflict", f"booking is {b['status']}")
            out = hs.create_booking(d, caller.org, caller.id, b["application_id"], b["interviewers"], s, b["duration_min"], b["title"], b["location"],
                                    b["notes"], at, replace=b["id"])
            audit(AGENT, "booking.rescheduled", caller.org, caller, booking=hid(caller.org, b["id"]), sequence=b["sequence"])
            return out
        out = hs.st().update(go)
        return ok(booking=out["booking"], invitation_draft_id=out["draft_id"], sent=False)

    @acts(AGENT, RECRUITING)
    def cancel_interview(self, caller, booking_id: str, reason: str = "") -> Dict[str, Any]:
        """Cancel: METHOD:CANCEL draft with SEQUENCE + 1. Frees the slot."""
        at = now()

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            b = _booking(d, caller.org, booking_id)
            if b["status"] != "confirmed":
                raise HiringError("conflict", f"booking is {b['status']}")
            audit(AGENT, "booking.cancelled", caller.org, caller, booking=hid(caller.org, b["id"]))
            b.update(status="cancelled", sequence=b["sequence"] + 1)
            b["history"].append({"at": at, "by": caller.id, "event": "cancel", "reason": str(reason)[:200]})
            dr = hs.draft(d, b, "cancel", hs.panel_for(d, caller.org, b["interviewers"]), caller.id, at)
            return {"booking": b, "invitation_draft_id": dr["id"]}
        return ok(sent=False, **hs.st().update(go))

    @acts(AGENT, RECRUITING)
    def complete_interview(self, caller, booking_id: str) -> Dict[str, Any]:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            b = _booking(d, caller.org, booking_id)
            if b["status"] != "confirmed" or b["start"] > now():
                raise HiringError("conflict", "only a confirmed interview whose start has passed can be completed")
            audit(AGENT, "booking.completed", caller.org, caller, booking=hid(caller.org, b["id"]))
            b["status"] = "completed"
            return b
        return ok(booking=hs.st().update(go))

    @acts(AGENT, RECRUITING)
    def mark_no_show(self, caller, booking_id: str, party: str, note: str = "") -> Dict[str, Any]:
        """Record that the candidate or an interviewer did not attend and draft a follow-up with the self-schedule link. This changes
        nothing about the application: a second candidate no-show is flagged for a person to decide."""
        if party not in ("candidate", "interviewer"):
            raise bad("party must be candidate or interviewer")
        at = now()

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            b = _booking(d, caller.org, booking_id)
            if b["status"] != "confirmed" or b["start"] > at:
                raise HiringError("conflict", "only a confirmed interview whose start has passed can be marked as a no-show")
            audit(AGENT, "booking.no_show", caller.org, caller, booking=hid(caller.org, b["id"]), party=party)
            b["status"] = f"no_show_{party}"
            b["history"].append({"at": at, "by": caller.id, "event": "no_show", "party": party, "note": str(note)[:200]})
            dr = hs.draft(d, b, "no_show_followup", hs.panel_for(d, caller.org, b["interviewers"]), caller.id, at)
            prior = sum(1 for x in hs.org_bookings(d, caller.org) if x["application_id"] == b["application_id"] and x["status"] == "no_show_candidate")
            flag = "second candidate no-show on this application: a person decides what happens next" if party == "candidate" and prior >= 2 else None
            return {"booking": b, "followup_draft_id": dr["id"], "flag": flag}
        out = hs.st().update(go)
        return ok(**out, note="A no-show is a fact for a person to weigh; the application's stage is unchanged.")

    @reads(AGENT, HIRING)
    def list_bookings(self, caller, application_id: str = "", upcoming_only: bool = False) -> Dict[str, Any]:
        rows = [b for b in hs.org_bookings(hs.st().load(), caller.org)
                if (not application_id or b["application_id"] == application_id) and (not upcoming_only or b["start"] > now())]
        return ok(bookings=sorted(rows, key=lambda b: b["start"]))

    # ---- drafts -----------------------------------------------------------------------------------------
    @reads(AGENT, HIRING)
    def list_drafts(self, caller, status: str = "draft") -> Dict[str, Any]:
        return ok(drafts=[x for x in mine(hs.st().load()["drafts"].values(), caller.org) if x["status"] == status])

    @acts(AGENT, RECRUITING)
    def approve_draft(self, caller, draft_id: str) -> Dict[str, Any]:
        """Approve an invitation draft. It is still not sent here: the mail layer sends approved drafts, filling the placeholders."""
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            x = d["drafts"].get(str(draft_id))
            if not x or x["org"] != caller.org:
                raise HiringError("not_found", "no such draft")
            if x["status"] != "draft":
                raise HiringError("conflict", f"draft is {x['status']}")
            audit(AGENT, "draft.approved", caller.org, caller, draft=hid(caller.org, draft_id), kind=x["kind"])
            x.update(status="approved", approved_by=caller.id)
            return x
        return ok(draft=hs.st().update(go), sent=False)

    @acts(AGENT, RECRUITING)
    def hand_off_to_mail(self, caller, draft_id: str) -> Dict[str, Any]:
        """Put an APPROVED invitation into the mailbox as a mail draft, addressed to the candidate (contact details come from ATS_CORE and
        only while consent holds). A person still has to read and send it from the mailbox: nothing is sent here. Once per draft."""
        sender = self.config.get("sender")
        if sender is None:
            raise HiringError("not_configured", "no mailbox is configured for drafts (set VELARIS_HR_MAILBOX_ID); the approved draft stays here")

        def claim(d: Dict[str, Any]) -> Dict[str, Any]:
            x = d["drafts"].get(str(draft_id))
            if not x or x["org"] != caller.org:
                raise HiringError("not_found", "no such draft")
            if x["status"] != "approved":
                raise HiringError("conflict", f"draft is {x['status']}; only an approved draft is handed to the mailbox")
            x["status"] = "handing_off"
            return dict(x)
        x = hs.st().update(claim)

        def release(status: str, **extra: Any) -> None:
            hs.st().update(lambda d: d["drafts"][x["id"]].update(status=status, **extra))
        try:
            contact = AtsCore().candidate_contact(candidate_id=x["to"]["candidate_id"])
            if contact.get("status") != "ok":
                release("approved")
                raise HiringError(contact.get("status", "denied"), f"the candidate's contact details are not available: {contact.get('reason', '')}")
            fill = lambda t: t.replace(hs.PLACEHOLDER_NAME, contact["name"]).replace(hs.PLACEHOLDER_EMAIL, contact["email"])
            body = fill(x["body"]).replace("\nTo pick another time or cancel: {schedule_link}\n", "")      # no link has been issued for this mail
            if sender.send(contact["email"], x["subject"], body) is not True:
                release("approved")
                raise HiringError("delivery_failed", "the mailbox did not accept the draft (no right to send from it, or no mailbox)")
        except HiringError:
            raise
        except Exception as e:
            logger.warning("hand-off of a draft failed: %s", type(e).__name__)
            release("approved")
            raise HiringError("error", "the draft could not be handed to the mailbox") from e
        audit(AGENT, "draft.handed_off", caller.org, caller, draft=hid(caller.org, draft_id), kind=x["kind"])
        release("handed_off", handed_off_by=caller.id, handed_off_at=now())
        return ok(draft_id=draft_id, handoff="handed_off", sent=False, note="drafted in the mailbox: a person must read and send it; the calendar file is not attached")

    @reads(AGENT, RECRUITING)
    def render_invitation(self, caller, draft_id: str, candidate_name: str, candidate_email: str) -> Dict[str, Any]:
        """The draft with the placeholders filled from values the caller supplies. Nothing is stored or sent."""
        x = hs.st().load()["drafts"].get(str(draft_id))
        if not x or x["org"] != caller.org:
            raise HiringError("not_found", "no such draft")
        name, email = hc.need_text(candidate_name, "candidate_name", 120), hc.need_text(candidate_email, "candidate_email", 254)
        if "@" not in email or any(c in email for c in "\r\n;<> "):
            raise bad("candidate_email is not usable")
        fill = lambda t: None if t is None else t.replace(hs.PLACEHOLDER_NAME, name).replace(hs.PLACEHOLDER_EMAIL, email)
        return ok(subject=x["subject"], body=fill(x["body"]), ics=fill(x["ics"]), still_a_draft=True)

    # ---- self-schedule and reminders -------------------------------------------------------------------------
    @acts(AGENT, RECRUITING)
    def issue_schedule_token(self, caller, application_id: str, interviewer_ids: List[str], duration_min: int, title: str,
                             location: str = "", days: int = 7, divergence_reason: str = "") -> Dict[str, Any]:
        """A link token for the candidate to pick (or move, or cancel) a slot with this panel. Returned once; stored hashed.
        Fair slots: every candidate at the same stage of the same requisition is offered the same recorded slot set. A different
        panel or length is refused unless an hr_admin passes `divergence_reason` (recorded with who and when)."""
        app = hc.application_known(caller.org, application_id)
        if not app or not app.get("candidate_id"):
            raise HiringError("not_found", "no such application")

        def go(d: Dict[str, Any]) -> str:
            hs.panel_for(d, caller.org, interviewer_ids)
            tok = hs.issue_token(d, app, interviewer_ids, duration_min, days, title, location, now(), caller.id,
                                 str(divergence_reason or ""), hc.HR_ADMIN in caller.roles)
            audit(AGENT, "schedule_token.issued", caller.org, caller, application=hid(caller.org, application_id),
                  divergence=bool(str(divergence_reason or "").strip()))
            return tok
        return ok(token=hs.st().update(go), valid_days=days, public_functions="velaris.agentkit.hiring_sched.public_slots / public_pick / public_cancel",
                  routes="GET /schedule/{token}/slots, POST /schedule/{token}/pick, POST /schedule/{token}/cancel (velaris.api.public)")

    @reads(AGENT, HIRING)
    def reminders(self, caller, within_hours: float = 24) -> Dict[str, Any]:
        """Reminders due (T-24h and T-1h before each confirmed interview) within the next `within_hours`, not yet marked sent."""
        return ok(reminders=hs.reminder_list(hs.st().load(), caller.org, now(), float(within_hours)))

    @acts(AGENT, RECRUITING)
    def mark_reminder_sent(self, caller, booking_id: str, kind: str) -> Dict[str, Any]:
        if kind not in [k for k, _ in hs.REMINDERS]:
            raise bad("kind must be T-24h or T-1h")

        def go(d: Dict[str, Any]) -> None:
            b = _booking(d, caller.org, booking_id)
            d["reminders_sent"][f"{b['id']}|{b['sequence']}|{kind}"] = now()
        hs.st().update(go)
        return ok(booking_id=booking_id, kind=kind)
