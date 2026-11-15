# EMPLOYEE_ONBOARDING

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/EMPLOYEE_ONBOARDING/main.py` (165 lines)

## Purpose

EMPLOYEE_ONBOARDING — Velaris BOS agent for Knackforge
Ported from VKatOS client_onboarding, adapted for employees (IT setup, HR docs, 30/60/90 day plan).

DEPRECATED (not served over HTTP, kept so existing databases stay readable; use ONBOARDING_FLOW). LEGACY: ONBOARDING_FLOW is the product with roles, sealed identifiers, retention and erasure. Until this older agent is merged into it or
retired (owner decision) every method needs an authenticated Caller (velaris.core.access): changes need the hr_admin role, reads go
through authorize_read("identity") (traced). Rows carry the organisation and every query filters on it; the database lives under
VELARIS_DATA, never in the working directory. A missing employee_id means "all of this organisation's", and 0 is not "all".
Raises AccessDenied when refused.

## Class `_EmployeeDB`

- `__init__(db_path)`
- `onboard(org, name, email, department, role)`
- `complete_step(org, employee_id, step_key)`
- `overdue(org)`
- `progress(org, employee_id)`

## Class `EmployeeOnboardingAgent`

Employee onboarding — IT setup, HR docs, team intro, 30/60/90 day plan.
Ported from VKatOS client_onboarding, adapted for employees.

- `__init__(config)`
- `health_check()`
- `onboard_employee(name, email, department, role)`
- `complete_step(employee_id, step_key)`
- `get_overdue()`
- `progress_report(employee_id)`

## Depends on

- `velaris.agentkit.onboarding_common`
- `velaris.core.sealed_sqlite`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/core/backfill_org.py`
- **tests:** `velaris/tests/test_hr_data_legacy.py`, `velaris/tests/test_no_state_in_source_tree.py`
