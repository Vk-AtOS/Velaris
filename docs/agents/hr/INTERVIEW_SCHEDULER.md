# INTERVIEW_SCHEDULER

- **Department:** `hr`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/hr/INTERVIEW_SCHEDULER/main.py` (283 lines)

## Purpose

INTERVIEW_SCHEDULER: who can interview when, bookings, invitations as drafts, self-scheduling, reminders, no-shows.

The slot algorithm and iCalendar builder are in velaris.agentkit.hiring_slots (stdlib, tested against hand-computed cases);
state and booking rules are in velaris.agentkit.hiring_sched. Invitations are DRAFTS: approve_draft marks one approved; hand_off_to_mail then
puts it in a mailbox as a mail DRAFT (config["sender"], velaris.agentkit.hr_wiring.MailDraftSender) for a person to read and send.
This agent never sends anything. The candidate side (public_slots, public_pick, public_cancel in
velaris.agentkit.hiring_sched) works from a hashed, expiring token and is not exposed in the identity-authenticated API.
A no-show is recorded and a follow-up drafted; it never rejects or withdraws anyone.

## Class `InterviewScheduler`

Slots, bookings, iCalendar invitations (as drafts), self-schedule tokens, reminders, no-shows.

- `__init__(config)`
- `health_check()`
- `set_availability(caller, interviewer_id, name, email, weekly, buffer_min, max_per_day, time_off)` — An interviewer's weekly hours (IST), buffer, daily maximum and time off [[start, end], ...]. Own record, or a recruiter's.
- `list_interviewers(caller)`
- `propose_slots(caller, interviewer_ids, duration_min, from_date, to_date, step_min, notice_hours)` — Free slots (UTC epoch plus IST text) where every listed interviewer is free.
- `book_interview(caller, application_id, interviewer_ids, start, duration_min, title, location, notes)` — Book a free slot (re-checked against every current booking: no double booking) and draft the invitation.
- `reschedule_interview(caller, booking_id, new_start)` — Move a booking: same UID, SEQUENCE + 1, a REQUEST draft.
- `cancel_interview(caller, booking_id, reason)` — Cancel: METHOD:CANCEL draft with SEQUENCE + 1. Frees the slot.
- `complete_interview(caller, booking_id)`
- `mark_no_show(caller, booking_id, party, note)` — Record that the candidate or an interviewer did not attend and draft a follow-up with the self-schedule link. This changes
- `list_bookings(caller, application_id, upcoming_only)`
- `list_drafts(caller, status)`
- `approve_draft(caller, draft_id)` — Approve an invitation draft. It is still not sent here: the mail layer sends approved drafts, filling the placeholders.
- `hand_off_to_mail(caller, draft_id)` — Put an APPROVED invitation into the mailbox as a mail draft, addressed to the candidate (contact details come from ATS_CORE and
- `render_invitation(caller, draft_id, candidate_name, candidate_email)` — The draft with the placeholders filled from values the caller supplies. Nothing is stored or sent.
- `issue_schedule_token(caller, application_id, interviewer_ids, duration_min, title, location, days, divergence_reason)` — A link token for the candidate to pick (or move, or cancel) a slot with this panel. Returned once; stored hashed.
- `reminders(caller, within_hours)` — Reminders due (T-24h and T-1h before each confirmed interview) within the next `within_hours`, not yet marked sent.
- `mark_reminder_sent(caller, booking_id, kind)`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.hiring_common`
- `velaris.agentkit.results`
- `velaris.agents.ATS_CORE.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/agentkit/hiring_common.py`, `velaris/agentkit/hiring_sched.py`, `velaris/agentkit/hr_wiring.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_api_public.py`, `velaris/tests/test_autonomy.py`, `velaris/tests/test_hiring_api.py`, `velaris/tests/test_hiring_scheduler.py`, `velaris/tests/test_hr_data_scheduler.py`
