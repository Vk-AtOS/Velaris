# LEAVE_MANAGEMENT

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/LEAVE_MANAGEMENT/main.py` (285 lines)

## Purpose

Leave management: leave requests, approval and balances for employees, with access control.

seed_balances(employee_id, year) (HR admins) creates default entitlements; get_balance(
employee_id, year), pending_approvals() and employee_history(employee_id, year=None) read
health-category data through authorize_read (own record or HR admin); apply(employee_id,
leave_type, from_date, to_date, reason) files a request over weekday-only days; approve and
reject(leave_id, reviewed_by) are HR-admin only, the reviewer must be the caller and may not
review their own leave. dsr_export and dsr_erase(org, subject_id, ...) serve data-subject
requests; erase is held (needs_review) while retention rules apply.
Failure: apply and review return {"error": ...} dicts (invalid_leave_type, invalid_date,
overlapping_leave when the days clash with a pending or approved request, no_balance_record,
insufficient_balance, unauthenticated, denied, access_denied, not_found, already_<status>,
self_approval_not_allowed); gated reads and changes raise through the access layer.
State: sqlite, encrypted at rest (velaris.core.sealed_sqlite), <VELARIS_DATA>/agents/LEAVE_MANAGEMENT/leaves.db (tables leave_requests,
leave_balances), scoped by organisation.

## Class `LeaveManagement`

Leave request lifecycle: apply → approve/reject → balance tracking.
Balances seeded from policy defaults; Zoho People sync optional.

- `__init__(config)`
- `health_check()`
- `seed_balances(employee_id, year)` — Seed default leave entitlements for a new employee/year (HR administrators).
- `get_balance(employee_id, year)` — Balances include sick leave, which is health data: your own, or an HR administrator's (authorize_read, traced).
- `apply(employee_id, leave_type, from_date, to_date, reason)`
- `approve(leave_id, reviewed_by)`
- `reject(leave_id, reviewed_by)`
- `pending_approvals(caller)`
- `employee_history(employee_id, year, caller)`
- `dsr_export(org, subject_id, links)` — Leave rows are health data: the person's own or an HR administrator's read (checked here, org from the verified caller).
- `dsr_erase(org, subject_id, on, links)` — Delete this person's leave rows when the retention registry allows (attendance and leave registers are a statutory class,

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.onboarding_common`
- `velaris.core.access`
- `velaris.core.sealed_sqlite`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `EMPLOYEE_RECORDS`
- **platform modules:** `velaris/api/allowlist.py`, `velaris/core/backfill_org.py`, `velaris/orchestration/autonomy.py`
- **tests:** `velaris/tests/test_autonomy.py`, `velaris/tests/test_caller_access.py`, `velaris/tests/test_deployment_org.py`, `velaris/tests/test_hr_data_records.py`, `velaris/tests/test_hr_wiring.py`, `velaris/tests/test_intel_tools.py`, `velaris/tests/test_kan68_backfill_org.py`, `velaris/tests/test_leave_and_api_trace.py`, `velaris/tests/test_manifests_health.py`, `velaris/tests/test_no_state_in_source_tree.py`, `velaris/tests/test_tool_unification.py`
