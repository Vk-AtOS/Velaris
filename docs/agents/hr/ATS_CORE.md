# ATS_CORE

- **Department:** `hr`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/hr/ATS_CORE/main.py` (447 lines)

## Purpose

ATS_CORE: requisitions, candidates, applications, pipeline, decision log, duplicates, erasure.

Two stores, on purpose (state under agent_dir("ATS_CORE"), owner-only, every record stamped with `org`):
  contacts.json     the person: name, e-mail, phone and the keys used for duplicate checks. Erasure deletes it.
  evaluation.json   requisitions, candidate stubs (id, source, consent), applications, stage history, the decision
                    log, duplicate review items. Holds no contact data, so after erasure it still answers "how many
                    applied, from where, how far they got" without describing anyone.

Rules in code: consent (purpose, notice version, future retention date) before anything about a person is stored;
stage moves only along TRANSITIONS; a rejection needs a reason code from a closed list; offer and hired need a
hiring manager or HR admin; a requisition is approved by someone other than its creator; the acting person is always
the authenticated Caller. A model has no method here that moves anyone: every state change is an `act` in the API
allowlist and waits for a person's approval. Contact reads and exports go through access.authorize_read("candidate") (hr_admin, recruiter).
The ledger (velaris.intel.trace) receives opaque hashes only.

## Class `AtsCore`

Applicant tracking core. See the module docstring.

- `__init__(config)`
- `health_check()`
- `create_requisition(caller, title, requirements, location, openings, department, employment_type, description)` — Draft a requisition. requirements: {"must": [{"skill": "python", "min_years": 2}], "nice": [...], "min_total_years": 3}.
- `approve_requisition(caller, requisition_id, note)` — Approve a draft requisition (not by its creator). Nothing can be opened or posted before this.
- `open_requisition(caller, requisition_id)` — Open an approved requisition for applications.
- `close_requisition(caller, requisition_id)` — Close an open requisition (filled or withdrawn).
- `get_requisition(caller, requisition_id)`
- `list_requisitions(caller, state)`
- `add_candidate(caller, name, consent, source, email, phone, profile_url, requisition_id, tracking_code)` — Store a candidate. consent {purpose, notice_version, retention_until, channel, talent_pool} is required first.
- `add_application(caller, candidate_id, requisition_id, source, tracking_code)` — Attach an existing candidate to another open requisition (their consent must still be valid).
- `move_stage(caller, application_id, to_stage, reason_code, note, evidence_refs)` — A person moves an application one allowed step and the decision log records who, what, why and when.
- `pipeline(caller, requisition_id)` — Applications of a requisition by stage, in order of arrival (not an ordering of merit).
- `get_application(caller, application_id)`
- `decision_log(caller, requisition_id)` — Who moved what, from where to where, and why. Entries are written only by people (the acting Caller).
- `aggregate_counts(caller, requisition_id)` — Applications by stage and by source. Includes people since erased: counts survive, identities do not.
- `duplicate_review(caller, status)` — Possible duplicates with the reasons (which fields agreed), never the contact values. Nothing merges by itself.
- `resolve_duplicate(caller, review_id, same_person, note)` — A person says the pair is the same person or not. This records the link; no record is merged or deleted.
- `withdraw_consent(caller, candidate_id)` — Record that the candidate withdrew consent (no login needed on their side). The candidate then shows in retention_due.
- `retention_due(caller)` — Candidates whose retention date has passed or whose consent was withdrawn. Lists only; deleting is erase_candidates,
- `candidate_contact(caller, candidate_id)` — Name and contact details of one candidate (recruiters and HR admins). access.authorize_read('candidate') decides and traces.
- `candidate_summary(caller, application_id)` — What the paperwork agents need about the person behind an application: name, contact, the role and the consent record
- `record_offer_outcome(caller, application_id, outcome, offer_id)` — Note on an application that its offer was accepted, declined, expired or withdrawn (OFFER_LETTERS calls this). It moves
- `export_candidate(caller, candidate_id)` — Everything held about one candidate (DPDP right to a summary), from this agent and every hiring module.
- `erase_candidates(caller, candidate_ids, reason)` — Erase people: contact data, résumé evidence, interview records, scorecard evidence text, decision notes.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.hiring_common`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `INTERVIEW_RECORD`, `INTERVIEW_SCHEDULER`, `JOB_POSTINGS`, `RECRUITMENT_ATS`, `RESUME_EVIDENCE`, `SCREENING_FORMS`
- **platform modules:** `velaris/agentkit/hiring_ats.py`, `velaris/agentkit/hiring_common.py`, `velaris/agentkit/hiring_forms.py`, `velaris/agentkit/hiring_intake.py`, `velaris/agentkit/hr_wiring.py`, `velaris/agentkit/onboarding_adapters.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_api_public.py`, `velaris/tests/test_hiring_api.py`, `velaris/tests/test_hiring_ats.py`, `velaris/tests/test_hiring_forms.py`, `velaris/tests/test_hiring_kit.py`, `velaris/tests/test_hiring_postings.py`, `velaris/tests/test_hiring_record.py`, `velaris/tests/test_hiring_resume.py`, `velaris/tests/test_hiring_scheduler.py`, `velaris/tests/test_hr_data_ats.py`, `velaris/tests/test_hr_wiring.py`, `velaris/tests/test_state_crossprocess.py`
