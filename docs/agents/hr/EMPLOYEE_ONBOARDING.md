# EMPLOYEE_ONBOARDING

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/EMPLOYEE_ONBOARDING/main.py` (152 lines)

## Purpose

EMPLOYEE_ONBOARDING — Velaris BOS agent for Knackforge
Ported from VKatOS client_onboarding, adapted for employees (IT setup, HR docs, 30/60/90 day plan).

## Class `_EmployeeDB`

- `__init__(db_path)`
- `onboard(name, email, department, role)`
- `complete_step(employee_id, step_key)`
- `overdue()`
- `progress(employee_id)`

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

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
