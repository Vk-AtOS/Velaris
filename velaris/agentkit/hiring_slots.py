"""Interview slots and iCalendar invitations, stdlib only.

Slots: each interviewer's weekly working hours are expanded into concrete intervals in Asia/Kolkata (UTC+05:30, no daylight
saving, so a fixed offset is exact), time off and existing bookings (widened by the buffer) are subtracted, days that reached
the interviewer's daily maximum are dropped, a panel is the intersection of its members' free time, and what is left is cut into
slots aligned to the local clock and no earlier than now + the minimum notice. Instants are UTC epoch seconds everywhere.

iCalendar: RFC 5545 text with the RFC 5546 scheduling methods. METHOD:REQUEST for a new or changed meeting, METHOD:CANCEL to cancel;
the UID stays the same for the life of the meeting and SEQUENCE goes up by one on every change (reschedule or cancel) so clients
replace the old copy. Text values are escaped and lines folded at 75 octets (RFC 5545 3.1, 3.3.11).
"""
from __future__ import annotations

import re
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from velaris.agentkit.hiring_common import DAY, bad

_CTRL = re.compile(r"[\x00-\x1f\x7f]")       # no control character (CR, LF, ...) can start a new ICS line

IST = timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
ACTIVE = ("proposed", "confirmed")
Interval = Tuple[float, float]
MAX_SPAN_DAYS = 31


def parse_weekly(weekly: Any) -> Dict[str, List[Tuple[str, str]]]:
    """{"mon": [["10:00","13:00"], ...]}: validated, windows sorted and non-overlapping."""
    if not isinstance(weekly, dict) or not weekly:
        raise bad("weekly working hours are required, e.g. {\"mon\": [[\"10:00\", \"17:00\"]]}")
    out: Dict[str, List[Tuple[str, str]]] = {}
    for day, wins in weekly.items():
        if day not in WEEKDAYS or not isinstance(wins, list) or len(wins) > 6:
            raise bad(f"weekly keys must be among {list(WEEKDAYS)} with at most 6 windows each")
        parsed = []
        for w in wins:
            try:
                a, b = (dtime.fromisoformat(x) for x in w)
            except (ValueError, TypeError) as e:
                raise bad("each window is [\"HH:MM\", \"HH:MM\"]") from e
            if not a < b:
                raise bad("a window must end after it starts")
            parsed.append((a.strftime("%H:%M"), b.strftime("%H:%M")))
        parsed.sort()
        if any(parsed[i][1] > parsed[i + 1][0] for i in range(len(parsed) - 1)):
            raise bad("windows of one day may not overlap")
        out[day] = parsed
    return out


def _local(d: date, hhmm: str) -> float:
    return datetime.combine(d, dtime.fromisoformat(hhmm), tzinfo=IST).timestamp()


def subtract(base: List[Interval], cut: Sequence[Interval]) -> List[Interval]:
    out = list(base)
    for cs, ce in cut:
        nxt: List[Interval] = []
        for s, e in out:
            if ce <= s or cs >= e:
                nxt.append((s, e))
                continue
            if s < cs:
                nxt.append((s, cs))
            if ce < e:
                nxt.append((ce, e))
        out = nxt
    return out


def intersect(a: List[Interval], b: List[Interval]) -> List[Interval]:
    out = [(max(s1, s2), min(e1, e2)) for s1, e1 in a for s2, e2 in b if max(s1, s2) < min(e1, e2)]
    return sorted(out)


def local_day(ts: float) -> date:
    return datetime.fromtimestamp(ts, IST).date()


def member_free(member: Dict[str, Any], bookings: Sequence[Dict[str, Any]], from_ts: float, to_ts: float) -> List[Interval]:
    """One interviewer's free intervals in [from_ts, to_ts]."""
    weekly = member["weekly"]
    buf = member.get("buffer_min", 10) * 60
    avail: List[Interval] = []
    d, last = local_day(from_ts), local_day(to_ts)
    mine = [b for b in bookings if member["id"] in b["interviewers"] and b["status"] in ACTIVE]
    per_day: Dict[date, int] = {}
    for b in mine:
        per_day[local_day(b["start"])] = per_day.get(local_day(b["start"]), 0) + 1
    while d <= last:
        if per_day.get(d, 0) < member.get("max_per_day", 4):
            avail += [(_local(d, a), _local(d, b)) for a, b in weekly.get(WEEKDAYS[d.weekday()], [])]
        d += timedelta(days=1)
    avail = subtract(avail, [tuple(t) for t in member.get("time_off", [])])
    avail = subtract(avail, [(b["start"] - buf, b["end"] + buf) for b in mine])
    return [(max(s, from_ts), min(e, to_ts)) for s, e in avail if max(s, from_ts) < min(e, to_ts)]


def propose_slots(panel: Sequence[Dict[str, Any]], bookings: Sequence[Dict[str, Any]], duration_min: int, from_ts: float, to_ts: float,
                  now_ts: float, step_min: int = 30, notice_h: float = 4, limit: int = 40) -> List[Dict[str, Any]]:
    if not panel:
        raise bad("at least one interviewer is needed")
    if isinstance(duration_min, bool) or not isinstance(duration_min, int) or not 10 <= duration_min <= 480:
        raise bad("duration_min must be 10 to 480")
    if isinstance(step_min, bool) or not isinstance(step_min, int) or not 5 <= step_min <= 120:
        raise bad("step_min must be 5 to 120")
    if not from_ts < to_ts <= from_ts + MAX_SPAN_DAYS * DAY:
        raise bad(f"the date range must be forward and at most {MAX_SPAN_DAYS} days")
    free = member_free(panel[0], bookings, from_ts, to_ts)
    for m in panel[1:]:
        free = intersect(free, member_free(m, bookings, from_ts, to_ts))
    earliest = now_ts + notice_h * 3600
    step, dur = step_min * 60, duration_min * 60
    off = IST.utcoffset(None).total_seconds()      # type: ignore[union-attr]
    slots: List[Dict[str, Any]] = []
    for s, e in free:
        t = max(s, earliest)
        t = ((t + off + step - 1) // step) * step - off          # align on the local wall clock
        while t + dur <= e and len(slots) < limit:
            slots.append({"start": t, "end": t + dur, "start_ist": datetime.fromtimestamp(t, IST).strftime("%a %d %b %Y %H:%M")})
            t += step
    return slots


def slot_is_free(panel: Sequence[Dict[str, Any]], bookings: Sequence[Dict[str, Any]], start: float, duration_min: int, now_ts: float,
                 notice_h: float = 4, ignore_booking: Optional[str] = None) -> bool:
    """Re-check one slot at booking time against the current bookings (the double-booking guard)."""
    others = [b for b in bookings if b["id"] != ignore_booking]
    day0 = datetime.fromtimestamp(start, IST).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    ok_slots = propose_slots(panel, others, duration_min, day0, day0 + DAY, now_ts, step_min=5, notice_h=notice_h, limit=1000)
    return any(abs(s["start"] - start) < 1 for s in ok_slots)


# ---- iCalendar --------------------------------------------------------------------------------------
def _esc(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "")


def _fold(line: str) -> str:
    raw, out, cur, n = line, [], "", 0
    for ch in raw:
        w = len(ch.encode("utf-8"))
        if n + w > (75 if not out else 74):
            out.append(cur)
            cur, n = "", 0
        cur, n = cur + ch, n + w
    out.append(cur)
    return "\r\n ".join(out)


def _utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(method: str, *, uid: str, sequence: int, start: float, end: float, stamp: float, summary: str, description: str,
              location: str, organizer: Tuple[str, str], attendees: Sequence[Tuple[str, str, str]]) -> str:
    """METHOD:REQUEST, CANCEL or PUBLISH (a copy for the candidate's own calendar, no attendees). organizer = (name, email); attendees = (name, email, role) with role REQ-PARTICIPANT or OPT-PARTICIPANT."""
    if method not in ("REQUEST", "CANCEL", "PUBLISH"):
        raise bad("method must be REQUEST, CANCEL or PUBLISH")
    if not (isinstance(sequence, int) and sequence >= 0) or not uid or not end > start:
        raise bad("sequence must be >= 0, uid non-empty and end after start")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Velaris//Hiring Scheduler 1.0//EN", "CALSCALE:GREGORIAN", f"METHOD:{method}",
             "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{_utc(stamp)}", f"DTSTART:{_utc(start)}", f"DTEND:{_utc(end)}", f"SEQUENCE:{sequence}",
             f"SUMMARY:{_esc(summary)}", f"DESCRIPTION:{_esc(description)}", f"LOCATION:{_esc(location)}",
             f"ORGANIZER;CN={_param(organizer[0])}:mailto:{organizer[1]}"]
    for name, email, role in attendees:
        lines.append(f"ATTENDEE;CN={_param(name)};ROLE={role};PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{_CTRL.sub('', str(email))}")
    lines += [f"STATUS:{'CANCELLED' if method == 'CANCEL' else 'CONFIRMED'}", "TRANSP:OPAQUE", "END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


def _param(v: str) -> str:
    v = _CTRL.sub(" ", str(v)).replace('"', "").replace(";", " ").replace(":", " ").replace(",", " ")
    return f'"{v}"'
