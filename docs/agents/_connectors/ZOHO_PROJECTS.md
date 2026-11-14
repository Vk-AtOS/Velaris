# ZOHO_PROJECTS

- **Department:** `_connectors`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_connectors/ZOHO_PROJECTS/main.py` (71 lines)

## Purpose

_No module docstring yet._

## Class `ZohoProjectsConnector`

Pulls project delivery data from Zoho Projects:
- Tasks assigned to each employee
- Completion rates and on-time delivery
- Time logged per employee per project
- Milestones and status

- `__init__(config)`
- `health_check()`
- `get_projects()`
- `get_tasks_by_owner(project_id, owner_id)`
- `get_timelogs(project_id, owner_id, from_date, to_date)` — Returns time logs for an employee in a project. Dates: MM-dd-yyyy
- `get_task_summary(project_id, owner_id)` — Returns task completion rate and on-time delivery for an employee.

## Depends on

- `velaris.agents.ZOHO_CONNECTOR.main`

## State and configuration

- keeps no files of its own
- env var: `ZOHO_PORTAL_ID`

## Called by

- **other agents:** `EMPLOYEE_METRICS_ENGINE`, `SPRINT_PLANNER`
- **platform modules:** none found
- **tests:** none found
