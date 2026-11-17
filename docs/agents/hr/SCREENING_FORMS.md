# SCREENING_FORMS

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/SCREENING_FORMS/main.py` (243 lines)

## Purpose

SCREENING_FORMS: intake forms and the staff side of candidate intake.

The public side (public_form, public_challenge, public_submit, public_status, public_withdraw) lives in
velaris.agentkit.hiring_intake as plain functions; PUBLIC_ROUTES in velaris.agentkit.hiring_forms lists the routes a gateway
would expose. They are deliberately NOT in the identity-authenticated API: a candidate holds a public form id, a solved
proof-of-work and later a hashed, expiring token, not an identity assertion.

Here, for staff (roles recruiter / hr_admin): define and publish forms, list pending submissions (no personal data in the
list), read one (identity data: authorize_read), accept it into ATS_CORE (which records consent and applies duplicate
review) or discard it, sweep expired ones, issue status/withdraw tokens, and process withdrawal requests.

## Class `ScreeningForms`

Intake forms (data), proof of work, upload checks, candidate tokens, and the staff side of intake.

- `__init__(config)`
- `health_check()`
- `create_form(caller, requisition_id, definition)` — definition: {title, fields:[{name,type,label,required,...}], consent_text, retention_days, talent_pool_offer, file_rules}.
- `publish_form(caller, form_id)` — Make a draft form available to the public intake route. Needs an open requisition.
- `unpublish_form(caller, form_id)`
- `list_forms(caller)`
- `get_form(caller, form_id)`
- `public_routes(caller)` — The routes served for candidates by velaris.api.public (a separate app), and why they are not in this API.
- `pending_submissions(caller)` — Waiting submissions: id, form, when, whether a file came. No personal data.
- `get_submission(caller, submission_id)`
- `accept_submission(caller, submission_id)` — A recruiter accepts a pending submission: ATS_CORE stores the candidate (consent from the form notice, duplicates go to
- `discard_submission(caller, submission_id)` — Delete a pending submission and its file.
- `sweep_submissions(caller)` — Delete pending submissions past their expiry (and their files). Consent that lapsed is not kept.
- `issue_candidate_token(caller, application_id, purpose, days)` — A status or withdraw token for an application. The raw token is returned once (put it in the candidate's e-mail); only
- `withdrawal_requests(caller)`
- `process_withdrawal(caller, application_id)` — Record the candidate's withdrawal of consent in ATS_CORE (they then show in retention_due for an approved erasure).

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.hiring_common`
- `velaris.agentkit.results`
- `velaris.agents.ATS_CORE.main`
- `velaris.agents.JOB_POSTINGS.main`
- `velaris.agents.RESUME_EVIDENCE.main`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/agentkit/hiring_common.py`, `velaris/agentkit/hiring_forms.py`, `velaris/agentkit/hiring_intake.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_api_public.py`, `velaris/tests/test_hiring_api.py`, `velaris/tests/test_hiring_forms.py`, `velaris/tests/test_hr_data_forms.py`, `velaris/tests/test_public_pages_browser.py`, `velaris/tests/test_sealed_binding.py`
