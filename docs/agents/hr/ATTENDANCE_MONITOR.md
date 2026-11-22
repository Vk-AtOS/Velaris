# ATTENDANCE_MONITOR

- **Department:** `hr`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/hr/ATTENDANCE_MONITOR/main.py` (90 lines)

## Purpose

Attendance monitor: reports who is present, late or absent from Zoho People attendance records.

check_today(employee_ids, date_str, caller=) returns {"present", "absent", "late", "unknown", "date"}: an employee with no
record is absent, one whose record has IsLate == "true" is late (with check-in), and one whose fetch failed (logged) is
"unknown", never absent. flag_absence_streaks(ids, from_date, to_date, threshold=3, caller=) flags employees with at least
threshold unexplained absences in the range (the days are counted, not checked for being consecutive); failed fetches
are skipped. Only a Status of "Absent" (or a record with no Status) is an unexplained absence. Approved leave, holidays,
weekly offs and work-from-home are explained: they are skip-neutral (they neither count towards the threshold nor
reset anything), so nobody is flagged for a day the organisation expected them away. Any other Status (Present,
half day, an unknown label) is not counted either: the monitor never flags on a label it does not recognise (VEL-55).
Lateness comes from Zoho's IsLate flag; there is no shift-start setting.
AccessDenied from the connector propagates. State: none kept here; data comes from ZohoPeopleConnector.

## Class `AttendanceMonitorAgent`

Real-time attendance monitoring.
Flags: late arrivals (Zoho's IsLate flag), unplanned absences, streak patterns.

- `__init__(config)`
- `health_check()`
- `check_today(employee_ids, date_str, caller)` — Returns today's attendance status for all employees. An employee whose record could not be fetched is `unknown`,
- `flag_absence_streaks(employee_ids, from_date, to_date, threshold, caller)` — Flags employees with >= threshold unexplained absences (see the module docstring for what is explained).

## Depends on

- `velaris.agents.ZOHO_PEOPLE.main`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_a.py`
