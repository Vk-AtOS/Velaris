# LEAVE_MANAGEMENT

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/LEAVE_MANAGEMENT/main.py` (273 lines)

## Purpose

_No module docstring yet._

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
- **platform modules:** `velaris/api/allowlist.py`, `velaris/core/backfill_org.py`
- **tests:** `velaris/tests/test_caller_access.py`, `velaris/tests/test_deployment_org.py`, `velaris/tests/test_hr_data_records.py`, `velaris/tests/test_hr_wiring.py`, `velaris/tests/test_kan68_backfill_org.py`, `velaris/tests/test_leave_and_api_trace.py`, `velaris/tests/test_no_state_in_source_tree.py`
