# ATTENDANCE_MONITOR

- **Department:** `hr`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/hr/ATTENDANCE_MONITOR/main.py` (71 lines)

## Purpose

_No module docstring yet._

## Class `AttendanceMonitorAgent`

Real-time attendance monitoring.
Flags: late arrivals (>15 min after shift start), unplanned absences, streak patterns.

- `__init__(config)`
- `health_check()`
- `check_today(employee_ids, date_str, caller)` — Returns today's attendance status for all employees. An employee whose record could not be fetched is `unknown`,
- `flag_absence_streaks(employee_ids, from_date, to_date, threshold, caller)` — Flags employees with consecutive absences >= threshold days.

## Depends on

- `velaris.agents.ZOHO_PEOPLE.main`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
