# LEAVE_MANAGEMENT

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/LEAVE_MANAGEMENT/main.py` (215 lines)

## Purpose

_No module docstring yet._

## Class `LeaveManagement`

Leave request lifecycle: apply → approve/reject → balance tracking.
Balances seeded from policy defaults; Zoho People sync optional.

- `__init__(config)`
- `health_check()`
- `seed_balances(employee_id, year)` — Seed default leave entitlements for a new employee/year.
- `get_balance(employee_id, year)`
- `apply(employee_id, leave_type, from_date, to_date, reason)`
- `approve(leave_id, reviewed_by)`
- `reject(leave_id, reviewed_by)`
- `pending_approvals(caller)`
- `employee_history(employee_id, year, caller)`

## Depends on

- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_caller_access.py`, `velaris/tests/test_deployment_org.py`, `velaris/tests/test_hr_wiring.py`, `velaris/tests/test_leave_and_api_trace.py`
