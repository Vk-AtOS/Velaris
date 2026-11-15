# ATTENDANCE_MONITOR

- **Department:** `hr`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/hr/ATTENDANCE_MONITOR/main.py` (80 lines)

## Purpose

Attendance monitor: reports who is present, late or absent from Zoho People attendance records.

check_today(employee_ids, date_str, caller=) returns {"present", "absent", "late", "unknown", "date"}: an employee with no
record is absent, one whose record has IsLate == "true" is late (with check-in), and one whose fetch failed (logged) is
"unknown", never absent. flag_absence_streaks(ids, from_date, to_date, threshold=3, caller=) flags employees with at least
threshold records whose Status is not "Present" in the range (the days are counted, not checked for being consecutive);
failed fetches are skipped. The shift_start_hour config is stored but not used; lateness comes from Zoho's IsLate flag.
AccessDenied from the connector propagates. State: none kept here; data comes from ZohoPeopleConnector.

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
- **tests:** `velaris/tests/test_agents_coverage_a.py`
