# JOB_POSTINGS

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/JOB_POSTINGS/main.py` (311 lines)

## Purpose

JOB_POSTINGS: publish a requisition without paying anyone.

  careers page   schema.org JobPosting JSON-LD (validated against the required fields), an HTML fragment, and the
                 Google Indexing API notification body. Building them sends nothing. send_indexing_notification is the
                 only method that goes out, and it is an `act`, refuses to run outside an approved flow step, takes its
                 token from SECRETS_VAULT (GOOGLE_INDEXING_ACCESS_TOKEN) and uses the same checked, pinned connection
                 as the Atlassian connectors (public addresses only, no redirects, only indexing.googleapis.com).
  posting packs  for every other board: text, fields, manual steps, a tracked link, a take-down date and task.
  approvals      a pack or posting is approved by someone other than whoever prepared it, and only an approved one can
                 be marked posted/live.
  tracking       each pack has a tracking code; resolve_tracking(code) gives the ATS `source` and requisition.

State under agent_dir("JOB_POSTINGS"); every record stamped with `org`; ledger entries hold hashes only.

## Class `JobPostings`

Job publishing: markup, indexing notice, posting packs, approvals, tracked links.

- `__init__(config)`
- `health_check()`
- `set_company_profile(caller, name, website, careers_base_url, contact_email)` — The hiring organisation as it appears in job markup. careers_base_url is where /jobs/<slug> pages are served.
- `get_company_profile(caller)`
- `prepare_careers_posting(caller, requisition_id, valid_through, salary)` — Build and validate the JobPosting JSON-LD, the careers fragment and the indexing body for an approved or open
- `get_posting(caller, posting_id)`
- `approve_posting(caller, posting_id)` — Approve the markup and text (not by whoever prepared it). Required before it can go live.
- `mark_posting_live(caller, posting_id)` — Record that the approved page is now published on the careers site.
- `take_down_posting(caller, posting_id)` — Record that the page was removed (or its validThrough set in the past); then send URL_DELETED.
- `send_indexing_notification(caller, posting_id, kind)` — Tell Google a job page changed (URL_UPDATED, needs a live posting) or was removed (URL_DELETED, needs a taken-down
- `prepare_pack(caller, posting_id, board)` — A pack for one board (text, fields, manual steps, tracked link, take-down date and task). Nothing is posted.
- `approve_pack(caller, pack_id)` — Approve a pack's text for pasting (not by whoever prepared it).
- `mark_pack_posted(caller, pack_id, live_url)` — A person says they pasted the approved pack on the board. Refused for a pack nobody approved.
- `mark_pack_taken_down(caller, pack_id)`
- `list_packs(caller, posting_id)`
- `takedown_due(caller, within_days)` — Posted packs whose take-down date is today, past, or within `within_days`: the tasks to do.
- `resolve_tracking(caller, code)` — The source (board) and requisition behind a tracking code: what to pass to ATS_CORE as `source` when an application

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.hiring_common`
- `velaris.agentkit.results`
- `velaris.agents.JIRA.atlassian`
- `velaris.agents.SECRETS_VAULT.main`
- `velaris.intel.web_fetch`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `SCREENING_FORMS`
- **platform modules:** `velaris/agentkit/hiring_common.py`, `velaris/agentkit/hiring_posting.py`, `velaris/agentkit/hiring_sched.py`, `velaris/api/allowlist.py`, `velaris/api/public.py`, `velaris/api/public_pages.py`
- **tests:** `velaris/tests/test_api_public.py`, `velaris/tests/test_hiring_api.py`, `velaris/tests/test_hiring_forms.py`, `velaris/tests/test_hiring_postings.py`, `velaris/tests/test_hiring_scheduler.py`, `velaris/tests/test_public_pages.py`
