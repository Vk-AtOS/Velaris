# ZOHO_PEOPLE

- **Department:** `_connectors`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_connectors/ZOHO_PEOPLE/main.py` (87 lines)

## Purpose

_No module docstring yet._

## Class `ZohoPeopleConnector`

Pulls employee data from Zoho People:
- Employee list and profiles
- Attendance records (daily clock-in/out, hours worked)
- Leave records (applied, approved, balance)
- Performance appraisal scores

- `__init__(config)`
- `health_check()`
- `get_employees(page, caller)` — Returns list of all employees with their full employee-form records.
- `get_attendance(employee_id, from_date, to_date)` — Returns attendance records for date range.
- `get_leave_summary(employee_id, year)` — Returns leave balance and taken days per leave type.
- `get_performance(employee_id)` — Returns appraisal records and scores for the employee.
- `get_attendance_summary(employee_id, from_date, to_date)` — Summarises attendance: total days, present, absent, late, avg hours/day.

## Depends on

- `velaris.agents.ZOHO_CONNECTOR.main`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ATTENDANCE_MONITOR`, `EMPLOYEE_METRICS_ENGINE`
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_caller_access.py`
