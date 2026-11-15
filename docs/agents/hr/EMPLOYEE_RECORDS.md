# EMPLOYEE_RECORDS

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/EMPLOYEE_RECORDS/main.py` (458 lines)

## Purpose

EMPLOYEE_RECORDS: the employee master, joining and leaving, and the data subject's export and erasure.

Conversion  A candidate becomes an employee only by a PROPOSAL from one HR administrator and an APPROVAL from a
            different one (four eyes). The consent given as a candidate is carried over with its purpose changed
            from "recruitment" to "employment" and the change recorded; the lawful basis (DPDP Act s.7(i),
            employment) is flagged for a lawyer because whether it covers the pre-employment stage is unsettled.
Changes     Only department, designation, manager and contact details change through change_record(), each with a
            who/why/when history row. Status changes only through the exit flow.
Exit        start_exit() produces the offboarding checklist and an access-revocation TASK list (one task per system
            named). This agent never changes a system: people do the tasks and tick them.
Erasure     erase_subject() asks the retention registry (velaris.agentkit.onboarding_retention) per class of data. Policy
            classes are erased. Statutory classes are HELD, and because no statutory period has been verified at a primary
            source the answer is `needs_review`: the person's name and employee id stay (to keep the statutory records
            readable), contact details and personal fields go, and the record becomes "restricted" rather than "erased".
            Counts by department and period survive in workforce_aggregate() without any personal data.
Reads       Personal fields come back only through authorize_read("identity"): the person's own record or an HR administrator.

## Class `EmployeeRecords`

The employee master with conversion, history, exit and data-subject rights. See the module docstring.

- `__init__(config)`
- `health_check()`
- `propose_conversion(application_id, department, designation, manager_id, join_date, offer_id, name, email)` — Propose turning a candidate into an employee (HR administrators). A different HR administrator must approve.
- `approve_conversion(conversion_id, note)` — Approve a proposal and create the employee (an HR administrator who did not propose it).
- `reject_conversion(conversion_id, reason)` — Reject a proposal (an HR administrator who did not propose it).
- `get_employee(employee_id)` — The employee record (identity access: the person's own record, or an HR administrator).
- `list_employees(status)` — Employees of the organisation (HR administrators): id, name, department, designation, manager, status.
- `employee_history(employee_id)` — Who changed what, when and why (identity access).
- `change_record(employee_id, field, new_value, reason)` — Change department, designation, manager, email or phone, with a reason (HR administrators). History keeps old and new.
- `workforce_aggregate()` — Counts by department, status and joining year, with no personal data; erased people are still counted (HR administrators).
- `start_exit(employee_id, last_working_day, reason_code, systems, it_owner_id, finance_owner_id)` — Start offboarding (HR administrators): the employee goes on notice and an exit checklist is produced, with one
- `complete_exit_task(exit_id, task_key, note)` — Tick an exit task (its assignee or an HR administrator); dependencies must be done first.
- `exit_status(exit_id)` — Exit checklist progress, blocked tasks and the access-revocation list (HR administrators and task assignees).
- `finalise_exit(exit_id)` — Close the exit once every required task is done (HR administrators): the employee becomes "exited".
- `retention_table()` — The retention registry as in force today. Statutory rows are unverified planning figures: `needs_review` is true for them.
- `retention_status(employee_id)` — For each class of data held about this person: erase or hold, and whether that needs review (identity access).
- `export_subject(employee_id)` — Everything held about a person (the person themselves or an HR administrator), identifiers masked.
- `erase_subject(employee_id, request_ref)` — Erase a former employee's personal data as far as the retention registry allows (HR administrators). `request_ref`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.onboarding_common`
- `velaris.agentkit.results`
- `velaris.agents.ESIGN.main`
- `velaris.agents.LEAVE_MANAGEMENT.main`
- `velaris.agents.OFFER_LETTERS.main`
- `velaris.agents.ONBOARDING_FLOW.main`
- `velaris.agents.PERFORMANCE_REVIEW_ENGINE.main`
- `velaris.agents.POLICY_ACKS.main`
- `velaris.core.access`
- `velaris.core.offboarding`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ATS_CORE`, `ESIGN`, `LEAVE_MANAGEMENT`, `OFFER_LETTERS`, `ONBOARDING_FLOW`, `PERFORMANCE_REVIEW_ENGINE`, `POLICY_ACKS`
- **platform modules:** `velaris/agentkit/hr_wiring.py`, `velaris/agentkit/onboarding_common.py`, `velaris/agentkit/onboarding_directory.py`, `velaris/agentkit/onboarding_dsr.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_hr_data_records.py`, `velaris/tests/test_hr_wiring.py`, `velaris/tests/test_onboarding_records.py`
