# TIME_TRACKER

- **Department:** `project_management`
- **Status (static inventory):** `real`
- **Source:** `departments/project_management/TIME_TRACKER/main.py` (165 lines)

## Purpose

_No module docstring yet._

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

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
