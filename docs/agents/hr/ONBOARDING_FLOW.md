# ONBOARDING_FLOW

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/ONBOARDING_FLOW/main.py` (545 lines)

## Purpose

ONBOARDING_FLOW: a checklist-and-task flow for a new joiner, plus minimal-data capture of the paperwork.

  * Tasks have an owner role, an assignee, a due date relative to the join date, and dependencies. A task whose
    dependency is open is BLOCKED; the status report names what each blocked task is waiting for.
  * Data capture (PAN, bank account, Aadhaar, documents, tax/PF/ESI forms) is only accepted for a task that is not
    blocked: nothing is collected before the offer is confirmed. Capture is DATA CAPTURE: no filing, no legal figure,
    and a format check is not verification (nothing calls UIDAI, NSDL or a bank).
  * PAN and bank account are AES-256-GCM sealed at rest (velaris.agentkit.onboarding_crypto, key under the data
    directory) and shown masked everywhere. The clear value comes back only from get_identifiers(reveal=True) after
    authorize_read("identity") for a PAN or ("bank") for an account. Aadhaar is never stored in full: only the last
    four digits and a keyed hash (why: onboarding_crypto docstring). Documents are stored sealed, content-hashed,
    with a deletion date set at collection from the retention registry.
  * Identity is the Caller. The new joiner acts on their own case (their employee id); HR administrators on any.
  * Every record carries the organisation; every read filters on it.
DPDP note: collecting for employment relies on the legitimate-use ground for employment (s.7(i)); whether it covers
a person before they are an employee is unsettled and needs a lawyer.

## Class `OnboardingFlow`

Onboarding cases: checklist tasks, minimal-data capture, masked identifiers. See the module docstring.

- `__init__(config)`
- `health_check()`
- `list_templates()` — The role groups and locations that have extra checklist items, and the base checklist.
- `start_onboarding(subject_id, name, email, join_date, role_group, location, manager_id, offer_id, it_owner_id, finance_owner_id)` — Open a case for a new joiner (HR administrators). `subject_id` is their employee id. Tasks are built from the
- `list_cases(status)` — Cases you may see: HR administrators all, others those they own tasks in or manage.
- `case_status(case_id)` — Completion percentage, every task's state, what is overdue and what is blocked (and by what). Identifiers masked.
- `reminders_due(within_days)` — Drafted reminders for tasks due within `within_days` or overdue, across open cases (HR administrators). Nothing is sent.
- `cancel_case(case_id, reason)` — Close a case that will not proceed (HR administrators).
- `complete_task(case_id, task_key, note, evidence_ref)` — Mark your task done (its assignee, or an HR administrator). Blocked tasks and data-capture tasks (which complete
- `waive_task(case_id, task_key, reason)` — Waive a task with a reason (HR administrators). Waived tasks count as complete and are listed as waived.
- `submit_identifier(case_id, kind, value, ifsc, purpose)` — Give your PAN, bank account (with IFSC) or Aadhaar (the new joiner or an HR administrator). The answer is masked.
- `get_identifiers(case_id, reveal)` — Masked identifiers of a case. With reveal=True the clear PAN (identity access) and bank account (bank access) are
- `check_aadhaar(case_id, number)` — Does this number match the stored Aadhaar? Only the new joiner or an HR administrator with identity access may ask.
- `submit_form(case_id, form, form_fields)` — Submit a data-capture form (tax declaration regime, PF/ESI nomination, emergency contact). Nothing is filed anywhere.
- `get_form(case_id, form)` — A submitted form's fields (identity access: the person's own, or an HR administrator).
- `collect_document(case_id, doc_type, filename, content_base64)` — Store a scanned document: sealed at rest, hashed, with a deletion date from the retention registry.
- `get_document(case_id, document_id)` — A collected document (base64), after authorize_read("identity"); its hash is re-checked on the way out.
- `dsr_export(org, subject_id, links)` — Everything this agent holds about a person, identifiers masked. The caller has already authorised the request.
- `dsr_erase(org, subject_id, on, links)` — Erase what the retention registry allows; hold the rest and say why. Returns {"erased": [...], "held": [...]}.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.onboarding_common`
- `velaris.agentkit.results`
- `velaris.core.access`
- `velaris.intel`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `EMPLOYEE_ONBOARDING`, `EMPLOYEE_RECORDS`, `OFFER_LETTERS`, `POLICY_ACKS`
- **platform modules:** `velaris/agentkit/hr_wiring.py`, `velaris/agentkit/onboarding_adapters.py`, `velaris/agentkit/onboarding_common.py`, `velaris/api/allowlist.py`, `velaris/orchestration/autonomy.py`
- **tests:** `velaris/tests/test_hr_data_legacy.py`, `velaris/tests/test_hr_data_onboarding.py`, `velaris/tests/test_hr_wiring.py`, `velaris/tests/test_onboarding_flow.py`, `velaris/tests/test_onboarding_records.py`
