# ZOHO_PEOPLE

- **Department:** `_connectors`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_connectors/ZOHO_PEOPLE/main.py` (102 lines)

## Purpose

Zoho People connector: reads employee, attendance, leave and appraisal data from the Zoho People API.

get_employees(page), get_attendance(employee_id, from_date, to_date) (MM-dd-yyyy),
get_leave_summary(employee_id, year=None), get_performance(employee_id) and
get_attendance_summary(...) call the API through ZOHO_CONNECTOR. Each takes an optional
keyword caller and first calls velaris.core.access.authorize_read (identity category, or
health for leave): the person's own record or an HR administrator may read, and an
unauthorised caller gets the exception authorize_read raises before any API call.
get_attendance_summary computes present/absent/late counts and average hours from the
records. A response without a result returns an empty list or dict. Keeps no state.

## Class `ZohoPeopleConnector`

Pulls employee data from Zoho People:
- Employee list and profiles
- Attendance records (daily clock-in/out, hours worked)
- Leave records (applied, approved, balance)
- Performance appraisal scores

- `__init__(config)`
- `health_check()`
- `get_employees(page, caller)` — Returns list of all employees with their full employee-form records.
- `get_attendance(employee_id, from_date, to_date, caller)` — Returns attendance records for date range.
- `get_leave_summary(employee_id, year, caller)` — Returns leave balance and taken days per leave type. Health access (sick and maternity leave are in it).
- `get_performance(employee_id, caller)` — Returns appraisal records and scores for the employee. Identity access.
- `get_attendance_summary(employee_id, from_date, to_date, caller)` — Summarises attendance: total days, present, absent, late, avg hours/day.

## Depends on

- `velaris.agents.ZOHO_CONNECTOR.main`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ATTENDANCE_MONITOR`, `EMPLOYEE_METRICS_ENGINE`
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_caller_access.py`
