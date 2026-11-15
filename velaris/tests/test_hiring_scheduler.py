"""INTERVIEW_SCHEDULER: slots (hand-computed), no double booking, iCalendar (parsed by a minimal parser), drafts, self-schedule, reminders, no-shows."""
import json
from datetime import datetime, timedelta

import pytest
from velaris.agentkit.hiring_testkit import ORG, advance, as_, bootstrap, clean_keys, consent, who

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_sched as hs
from velaris.agentkit import hiring_slots as sl
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.agents.INTERVIEW_SCHEDULER.main import InterviewScheduler
from velaris.agents.JOB_POSTINGS.main import JobPostings
from velaris.intel.paths import agent_dir

WEEKLY = {"mon": [["10:00", "13:00"], ["14:00", "18:00"]], "tue": [["10:00", "13:00"]]}


def next_monday():
    d = (datetime.now(sl.IST) + timedelta(days=3)).date()
    while d.weekday() != 0:
        d += timedelta(days=1)
    return d


MON = next_monday()


def at(hhmm, day=MON):
    return f"{day.isoformat()}T{hhmm}"            # no offset: Asia/Kolkata local time


def ts(hhmm, day=MON):
    return datetime.fromisoformat(f"{day.isoformat()}T{hhmm}").replace(tzinfo=sl.IST).timestamp()


def utc(epoch):
    return datetime.fromtimestamp(epoch, sl.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_ics(text):
    """A minimal RFC 5545 reader: checks CRLF and the 75-octet limit, unfolds, returns the calendar and VEVENT properties."""
    assert text.endswith("\r\n") and "\n" not in text.replace("\r\n", "")
    raw = text[:-2].split("\r\n")
    assert all(len(line.encode()) <= 75 for line in raw), "a line is longer than 75 octets"
    lines = []
    for line in raw:
        if line.startswith(" "):
            lines[-1] += line[1:]
        else:
            lines.append(line)
    assert lines[0] == "BEGIN:VCALENDAR" and lines[-1] == "END:VCALENDAR"
    out, stack = {"props": {}, "attendees": []}, []
    for line in lines:
        head, _, value = line.partition(":")
        name = head.split(";")[0]
        if name == "BEGIN":
            stack.append(value)
        elif name == "END":
            assert stack.pop() == value
        elif stack == ["VCALENDAR"]:
            out[name.lower()] = value
        elif name == "ATTENDEE":
            out["attendees"].append(value)
        else:
            out["props"][name] = value
    assert not stack
    return out


def unesc(v):
    return v.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


@pytest.fixture()
def env():
    ats, sch = AtsCore(), InterviewScheduler()
    rid, c = bootstrap(ats)
    with as_(c["rec"]):
        JobPostings().set_company_profile(name="Chennai Tech", website="https://cts.example", careers_base_url="https://cts.example/c", contact_email="hr@cts.example")
        apps = []
        for i in range(3):
            r = ats.add_candidate(name=f"Person Number{i}", email=f"p{i}@example.com", phone=f"+91 9{i}000 1234{i}", source="careers_page", requisition_id=rid, consent=consent())
            apps.append(r["application"]["id"])
        for iid, name in (("iv-a", "Anita Rao"), ("iv-b", "Bala Kumar")):
            assert sch.set_availability(interviewer_id=iid, name=name, email=f"{iid}@cts.example", weekly=WEEKLY, buffer_min=10, max_per_day=3)["status"] == "ok"
    return ats, sch, rid, apps, c


def starts(r):
    return [datetime.fromtimestamp(s["start"], sl.IST).strftime("%H:%M") for s in r["slots"]]


def book(sch, app, who_, hhmm, title="x", day=MON, dur=60, **kw):
    return sch.book_interview(application_id=app, interviewer_ids=who_, start=at(hhmm, day), duration_min=dur, title=title, **kw)


def free(sch, who_, day=MON, dur=60):
    return sch.propose_slots(interviewer_ids=who_, duration_min=dur, from_date=at("00:00", day), to_date=at("23:59", day))


def test_slots_with_buffers_around_an_existing_booking_hand_computed(env):
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        assert book(sch, apps[0], ["iv-a"], "11:00", "Tech round")["status"] == "ok"
        r = free(sch, ["iv-a"])
    # busy 11:00-12:00 widened by the 10-minute buffer = 10:50-12:10; free 10:00-10:50 (too short), 12:10-13:00 (no aligned 60-minute slot), 14:00-18:00
    assert starts(r) == ["14:00", "14:30", "15:00", "15:30", "16:00", "16:30", "17:00"]
    assert r["timezone"] == "Asia/Kolkata" and r["slots"][0]["start_ist"].endswith("14:00") and r["slots"][0]["start"] == ts("14:00")


def test_panel_intersection_daily_maximum_time_off_and_notice(env):
    ats, sch, rid, apps, c = env
    tue = MON + timedelta(days=1)
    with as_(c["rec"]):
        sch.set_availability(interviewer_id="iv-c", name="Chitra", email="c@cts.example", weekly={"mon": [["12:00", "16:00"]]}, buffer_min=0)
        assert starts(free(sch, ["iv-a", "iv-c"])) == ["12:00", "14:00", "14:30", "15:00"]          # 12-13 and 14-16 are free for both
        sch.set_availability(interviewer_id="iv-d", name="Devi", email="d@cts.example", weekly=WEEKLY, buffer_min=0, max_per_day=1)
        assert book(sch, apps[0], ["iv-d"], "10:00")["status"] == "ok"
        assert free(sch, ["iv-d"])["slots"] == []                                                    # one a day: Monday is full
        assert book(sch, apps[1], ["iv-d"], "15:00")["status"] == "conflict"
        assert len(free(sch, ["iv-d"], tue)["slots"]) == 5                                           # Tuesday 10-13 in 30-minute steps
        sch.set_availability(interviewer_id="iv-a", name="Anita Rao", email="iv-a@cts.example", weekly=WEEKLY, time_off=[[at("00:00"), at("23:59")]])
        assert free(sch, ["iv-a"])["slots"] == []                                                    # time off removes the day
    # minimum notice, and alignment on the local clock (India is UTC+05:30)
    member = {"id": "x", "weekly": sl.parse_weekly({"mon": [["09:00", "12:00"]]}), "buffer_min": 0, "max_per_day": 9}
    slots = sl.propose_slots([member], [], 30, ts("00:00"), ts("23:59"), ts("09:10"), step_min=30, notice_h=1)
    assert [datetime.fromtimestamp(s["start"], sl.IST).strftime("%H:%M") for s in slots] == ["10:30", "11:00", "11:30"]   # 10:10 is the earliest, so the next :30


def test_no_double_booking_even_for_the_same_instant_or_the_buffer(env):
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        first = book(sch, apps[0], ["iv-a", "iv-b"], "14:00", "Panel")
        assert first["status"] == "ok" and first["sent"] is False
        assert book(sch, apps[1], ["iv-a"], "14:00")["status"] == "conflict"
        assert book(sch, apps[1], ["iv-b"], "14:30")["status"] == "conflict"                         # overlaps
        assert book(sch, apps[1], ["iv-b"], "15:05")["status"] == "conflict"                         # inside the 10-minute buffer
        assert book(sch, apps[1], ["iv-b"], "15:10")["status"] == "ok"                               # just clear of it
        assert book(sch, apps[2], ["iv-a"], "08:00")["status"] == "conflict"                         # outside working hours
        assert book(sch, "app-nope", ["iv-a"], "16:00")["status"] == "not_found"
        assert book(sch, apps[2], ["iv-zzz"], "16:00")["status"] == "not_found"
        assert book(sch, apps[2], ["iv-a"], "16:00", dur=5)["status"] == "invalid_input"
        assert sch.book_interview(application_id=apps[2], interviewer_ids=["iv-a"], start="whenever", duration_min=60, title="x")["status"] == "invalid_input"


def test_icalendar_request_reschedule_and_cancel_are_parseable_with_stable_uid_and_rising_sequence(env):
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        b = book(sch, apps[0], ["iv-a", "iv-b"], "14:00", "Tech round; Python, SQL", dur=45, location="Meet, link: https://meet.example/x",
                 notes="Bring a laptop.\nSecond line")
        d1 = sch.list_drafts()["drafts"][0]
    uid, booking = b["booking"]["uid"], b["booking"]
    ics = parse_ics(d1["ics"])
    assert ics["method"] == "REQUEST" and ics["version"] == "2.0" and ics["props"]["UID"] == uid and ics["props"]["SEQUENCE"] == "0"
    assert ics["props"]["DTSTART"] == utc(ts("14:00")) and ics["props"]["DTEND"] == utc(ts("14:45"))
    assert unesc(ics["props"]["SUMMARY"]) == "Tech round; Python, SQL" and unesc(ics["props"]["DESCRIPTION"]) == "Bring a laptop.\nSecond line"
    assert unesc(ics["props"]["LOCATION"]) == "Meet, link: https://meet.example/x" and ics["props"]["STATUS"] == "CONFIRMED"
    assert ics["props"]["ORGANIZER"] == "mailto:hr@cts.example"
    assert set(ics["attendees"]) == {"mailto:iv-a@cts.example", "mailto:iv-b@cts.example", "mailto:{candidate_email}"}
    with as_(c["rec"]):
        moved = sch.reschedule_interview(booking_id=booking["id"], new_start=at("16:00"))["booking"]
        re_draft = [d for d in sch.list_drafts()["drafts"] if d["kind"] == "reschedule"][0]
    re_ics = parse_ics(re_draft["ics"])
    assert re_ics["method"] == "REQUEST" and re_ics["props"]["UID"] == uid and re_ics["props"]["SEQUENCE"] == "1" and re_ics["props"]["DTSTART"] == utc(ts("16:00"))
    with as_(c["rec"]):
        assert sch.cancel_interview(booking_id=moved["id"], reason="role on hold")["status"] == "ok"
        assert sch.cancel_interview(booking_id=moved["id"])["status"] == "conflict"
        cx = [d for d in sch.list_drafts()["drafts"] if d["kind"] == "cancel"][0]
        reopened = free(sch, ["iv-a"])
    can = parse_ics(cx["ics"])
    assert can["method"] == "CANCEL" and can["props"]["UID"] == uid and can["props"]["SEQUENCE"] == "2" and can["props"]["STATUS"] == "CANCELLED"
    assert "16:00" in starts(reopened)                                                                # the cancelled slot is free again


def test_line_folding_and_escaping_follow_rfc5545():
    title = "நேர்காணல் " * 12 + "a\\b;c,d"
    ics = sl.build_ics("REQUEST", uid="u1@x", sequence=0, start=1_900_000_000, end=1_900_003_600, stamp=1_800_000_000, summary=title, description="x" * 300,
                       location="Chennai", organizer=('Org "Q": name', "o@x.example"), attendees=[("Ann", "a@x.example", "REQ-PARTICIPANT")])
    parsed = parse_ics(ics)                                                      # asserts every physical line is at most 75 octets and CRLF-terminated
    assert unesc(parsed["props"]["SUMMARY"]) == title and parsed["props"]["DESCRIPTION"] == "x" * 300
    assert 'ORGANIZER;CN="Org Q  name":mailto:o@x.example' in ics.replace("\r\n ", "")
    for kw in ({"method": "PUBLISH", "sequence": 0}, {"method": "REQUEST", "sequence": -1}):
        with pytest.raises(hc.HiringError):
            sl.build_ics(kw["method"], uid="u", sequence=kw["sequence"], start=1, end=2, stamp=0, summary="s", description="d", location="l", organizer=("o", "o@x"), attendees=[])


def test_invitations_are_drafts_until_approved_and_never_hold_the_candidates_email(env):
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        did = book(sch, apps[0], ["iv-a"], "14:00", "Round 1")["invitation_draft_id"]
        d = sch.list_drafts()["drafts"][0]
        assert d["status"] == "draft" and d["sent"] is False and "{candidate_name}" in d["body"] and "p0@example.com" not in json.dumps(d)
        r = sch.render_invitation(draft_id=did, candidate_name="Person Number0", candidate_email="p0@example.com")
        assert "Hello Person Number0" in r["body"] and "mailto:p0@example.com" in r["ics"] and r["still_a_draft"] is True
        assert sch.render_invitation(draft_id=did, candidate_name="X", candidate_email="a@b.c\r\nBcc: evil@x")["status"] == "invalid_input"
        assert sch.approve_draft(draft_id=did)["sent"] is False
        assert sch.approve_draft(draft_id=did)["status"] == "conflict"
    assert "p0@example.com" not in (agent_dir("INTERVIEW_SCHEDULER") / "scheduler.json").read_text()


def test_invitation_needs_an_organizer_address(env):
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        # drop the company profile's contact address: booking is refused and nothing is left behind
        JobPostings().set_company_profile(name="Chennai Tech", website="https://cts.example", careers_base_url="https://cts.example/c", contact_email="")
        assert book(sch, apps[0], ["iv-a"], "14:00")["status"] == "not_configured"
        assert sch.list_bookings()["bookings"] == []


def test_candidate_self_schedule_token_pick_move_cancel(env, monkeypatch):
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        tok = sch.issue_schedule_token(application_id=apps[0], interviewer_ids=["iv-a"], duration_min=60, title="Round 1", days=3)["token"]
        assert sch.issue_schedule_token(application_id=apps[0], interviewer_ids=["iv-zzz"], duration_min=60, title="x")["status"] == "not_found"
        assert sch.issue_schedule_token(application_id=apps[0], interviewer_ids=["iv-a"], duration_min=60, title="x", days=99)["status"] == "invalid_input"
    raw = (agent_dir("INTERVIEW_SCHEDULER") / "scheduler.json").read_text()
    assert tok not in raw and hc.sha(tok) in raw
    offered = hs.public_slots(tok)
    assert offered["status"] == "ok" and offered["slots"] and len(offered["slots"]) == len(offered["starts"])
    first, third = offered["starts"][0], offered["starts"][2]
    assert hs.public_pick(tok, first)["status"] == "ok"
    with as_(c["rec"]):
        bk = sch.list_bookings()["bookings"]
    assert len(bk) == 1 and bk[0]["sequence"] == 0 and bk[0]["created_by"] == "candidate-token"
    assert hs.public_pick(tok, first + 60)["status"] == "conflict"                 # not a free aligned slot
    assert hs.public_pick(tok, third)["status"] == "ok"                            # picking again moves the booking
    with as_(c["rec"]):
        bk = sch.list_bookings()["bookings"]
        kinds = sorted(d["kind"] for d in sch.list_drafts()["drafts"])
        assert sch.book_interview(application_id=apps[1], interviewer_ids=["iv-a"], start=hc.iso(third), duration_min=60, title="x")["status"] == "conflict"
    assert len(bk) == 1 and bk[0]["sequence"] == 1 and bk[0]["start"] == third and kinds[:2] == ["invite", "reschedule"]
    assert hs.public_cancel(tok)["status"] == "ok" and hs.public_cancel(tok)["status"] == "not_found"
    assert hs.public_slots("x" * 30)["status"] == "not_found" and hs.public_pick(None, 1)["status"] == "not_found"
    advance(monkeypatch, 4 * hc.DAY)
    assert hs.public_slots(tok)["status"] == "not_found"                           # expired


def test_reminders_and_marking_them_sent(env, monkeypatch):
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        bid = book(sch, apps[0], ["iv-a"], "14:00")["booking"]["id"]
        assert sch.reminders(within_hours=1)["reminders"] == []
    advance(monkeypatch, (ts("14:00") - hc.now()) - 23 * 3600)                    # 23 hours before: the T-24h reminder is overdue
    with as_(c["rec"]):
        due = sch.reminders(within_hours=0.5)["reminders"]
        assert [r["kind"] for r in due] == ["T-24h"] and due[0]["overdue"] and due[0]["booking_id"] == bid
        assert sch.mark_reminder_sent(booking_id=bid, kind="T-24h")["status"] == "ok"
        assert sch.mark_reminder_sent(booking_id=bid, kind="T-5m")["status"] == "invalid_input"
        assert sch.reminders(within_hours=0.5)["reminders"] == []
        assert [r["kind"] for r in sch.reminders(within_hours=24)["reminders"]] == ["T-1h"]


def test_no_show_is_recorded_without_touching_the_application(env, monkeypatch):
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        b1 = book(sch, apps[0], ["iv-a"], "14:00")["booking"]["id"]
        assert sch.mark_no_show(booking_id=b1, party="candidate")["status"] == "conflict"             # it has not started yet
    advance(monkeypatch, ts("16:00") - hc.now())
    with as_(c["rec"]):
        r = sch.mark_no_show(booking_id=b1, party="candidate", note="no call")
        assert r["status"] == "ok" and r["booking"]["status"] == "no_show_candidate" and r["flag"] is None and "stage is unchanged" in r["note"]
        assert any(d["kind"] == "no_show_followup" and "{schedule_link}" in d["body"] for d in sch.list_drafts()["drafts"])
        assert sch.mark_no_show(booking_id=b1, party="nobody")["status"] == "invalid_input"
        assert sch.mark_no_show(booking_id=b1, party="candidate")["status"] == "conflict"
        assert ats.aggregate_counts()["by_stage"] == {"applied": 3}                                   # nobody was rejected or withdrawn
        assert sch.reschedule_interview(booking_id=b1, new_start=at("17:00", MON + timedelta(days=7)))["status"] == "ok"


def test_availability_roles_org_stamping_and_clean_output(env):
    ats, sch, rid, apps, c = env
    with as_(who("interviewer", id="iv-z")):
        assert sch.set_availability(interviewer_id="iv-a", name="x", email="a@b.c", weekly=WEEKLY)["status"] == "denied"      # only your own
        assert sch.set_availability(interviewer_id="iv-z", name="Zed", email="z@cts.example", weekly=WEEKLY)["interviewer"]["org"] == ORG
        for bad in ({"mon": [["12:00", "10:00"]]}, {"mon": [["10:00", "13:00"], ["12:00", "14:00"]]}, {"funday": [["10:00", "11:00"]]}, {}):
            assert sch.set_availability(interviewer_id="iv-z", name="Zed", email="z@cts.example", weekly=bad)["status"] == "invalid_input"
        assert sch.set_availability(interviewer_id="iv-z", name="Zed", email="nope", weekly=WEEKLY)["status"] == "invalid_input"
        assert book(sch, apps[0], ["iv-z"], "10:00")["status"] == "denied"                            # interviewers do not book
    assert sch.list_interviewers()["status"] == "unauthenticated"
    with as_(who("recruiter", org="other")):
        assert sch.list_interviewers()["interviewers"] == [] and sch.list_bookings()["bookings"] == []
    with as_(c["rec"]):
        clean_keys(free(sch, ["iv-a"]))
        assert sch.propose_slots(interviewer_ids=["iv-a"], duration_min=60, from_date=at("00:00"), to_date=at("23:59", MON + timedelta(days=60)))["status"] == "invalid_input"


def test_erasure_keeps_capacity_history_and_drops_the_candidate(env):
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        book(sch, apps[0], ["iv-a"], "14:00", "R", notes="Asha mentioned a bereavement")
        cid = json.loads((agent_dir("ATS_CORE") / "evaluation.json").read_text())["applications"][apps[0]]["candidate_id"]
        sch.issue_schedule_token(application_id=apps[0], interviewer_ids=["iv-a"], duration_min=60, title="x")
    with as_(c["adm"]):
        assert ats.erase_candidates(candidate_ids=[cid], reason="erasure_request")["removed_by_module"]["hiring_sched"] == 3       # draft, token, booking
    st = json.loads((agent_dir("INTERVIEW_SCHEDULER") / "scheduler.json").read_text())
    assert st["drafts"] == {} and st["tokens"] == {}
    b = list(st["bookings"].values())[0]
    assert b["candidate_id"] is None and b["application_id"] is None and b["notes"] == "" and b["org"] == ORG and b["start"] == ts("14:00")


def test_fair_slots_same_set_per_stage_round_and_divergence_needs_an_hr_admin_reason(env, monkeypatch):
    ats, sch, rid, apps, c = env
    tok = lambda a, who_=("iv-a",), **kw: sch.issue_schedule_token(application_id=a, interviewer_ids=list(who_), duration_min=kw.pop("dur", 60), title="R1", days=kw.pop("days", 3), **kw)
    with as_(c["rec"]):
        t0, t1 = tok(apps[0])["token"], tok(apps[1])["token"]
        assert hs.public_slots(t0)["starts"] == hs.public_slots(t1)["starts"] and hs.public_slots(t0)["starts"]
        assert tok(apps[2], ("iv-b",))["status"] == "conflict"                              # a different panel: not the same slots
        assert tok(apps[2], dur=30)["status"] == "conflict"                                 # a different length too
        assert tok(apps[2], ("iv-b",), divergence_reason="needs the security lead")["status"] == "denied"   # recruiters cannot divert
        assert tok(apps[2], divergence_reason="why")["status"] == "invalid_input"           # a reason only for a divergent token
    with as_(c["adm"]):
        assert tok(apps[2], ("iv-b",))["status"] == "conflict"                              # even an hr_admin needs the reason
        t2 = tok(apps[2], ("iv-b",), divergence_reason="  ")["status"]
        assert t2 == "conflict"
        t2 = tok(apps[2], ("iv-b",), divergence_reason="candidate needs the security lead")["token"]
    rnd = list(json.loads((agent_dir("INTERVIEW_SCHEDULER") / "scheduler.json").read_text())["rounds"].values())
    assert len(rnd) == 1 and rnd[0]["exceptions"][0]["by"] == c["adm"].id and rnd[0]["exceptions"][0]["reason"].startswith("candidate needs")
    assert rnd[0]["exceptions"][0]["at"] > 0 and rnd[0]["panel"] == ["iv-a"]
    # a slot taken by one candidate leaves everyone else's set, nothing else changes
    s0 = hs.public_slots(t0)["starts"]
    assert hs.public_pick(t0, s0[0])["status"] == "ok"
    assert hs.public_slots(t1)["starts"] == [x for x in hs.public_slots(t0)["starts"]] and s0[0] not in hs.public_slots(t1)["starts"]
    assert hs.public_pick(t1, s0[0] + 1800 * 100)["status"] == "conflict"                  # not on the offered list
    # a new stage is a new round; an expired round is a new round
    with as_(c["rec"]):
        assert ats.move_stage(application_id=apps[1], to_stage="screening")["status"] == "ok"
        assert tok(apps[1], ("iv-b",))["status"] == "ok"
    advance(monkeypatch, 4 * hc.DAY)
    with as_(c["rec"]):
        assert tok(apps[0], ("iv-b",))["status"] == "ok"


def test_ics_text_fields_cannot_inject_lines():
    """KAN-64 review: CR was not stripped from names and the e-mail was not escaped."""
    from velaris.agentkit import hiring_slots as sl
    ics = sl.build_ics("REQUEST", uid="u1", sequence=0, start=0, end=3600, stamp=0, summary="s", description="d", location="l",
                       organizer=("Org", "o@x.com"), attendees=[("Eve\rATTENDEE:mailto:evil@x.com\r\nBEGIN:VALARM", "a@x.com\r\nX-EVIL:1", "REQ-PARTICIPANT")])
    assert not any(line.startswith(("X-EVIL", "BEGIN:VALARM", "ATTENDEE;CN=\"Eve\rATTENDEE")) for line in ics.splitlines())
    assert "\r" not in ics.replace("\r\n", "")
