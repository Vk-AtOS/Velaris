# TIME_TRACKER

- **Department:** `project_management`
- **Status (static inventory):** `real`
- **Source:** `departments/project_management/TIME_TRACKER/main.py` (183 lines)

## Purpose

Time tracker: billable hours and utilization per employee and project.
TimeTracker.start_timer(employee_id, project_id, task_id, description) starts a timer, first
stopping and logging any running one for that employee. stop_timer(employee_id, billable=True)
logs the elapsed hours, capped at 24 (a timer left running is not logged as days). log(employee_id, project_id, hours, log_date, task_id, description,
billable) adds a manual entry. weekly_utilization(employee_id, week_start) returns total, billable
and per-project hours and utilization against a billable target (config billable_target_weekly,
default 40). team_utilization(employee_ids, week_start) maps that over employees.
project_hours_summary(project_id, from_date, to_date) returns hours per contributor.
State: sqlite database <VELARIS_DATA>/agents/TIME_TRACKER/timelog.db (tables timelogs and
active_timers). Failure: stop_timer with no timer returns {"error": "no_active_timer"}; log rejects
non-numeric, non-finite, zero, negative or over-24 hours with an error dict; other input is not
validated, and there is no caller check. The Zoho integration is not implemented here.

## Class `TimeTracker`

Billable hours and utilization tracking per employee and project.
Supports start/stop timer, manual log entry, weekly utilization reports.
Integrates with Zoho Projects time logs when configured.

- `__init__(config)`
- `health_check()`
- `start_timer(employee_id, project_id, task_id, description)`
- `stop_timer(employee_id, billable)`
- `log(employee_id, project_id, hours, log_date, task_id, description, billable)`
- `weekly_utilization(employee_id, week_start)` — week_start: ISO date of Monday
- `team_utilization(employee_ids, week_start)`
- `project_hours_summary(project_id, from_date, to_date)`

## Depends on

- `velaris.core.sqlite_util`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_kan94_pm_agents.py`, `velaris/tests/test_no_state_in_source_tree.py`
