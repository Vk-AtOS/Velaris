# ZOHO_PROJECTS

- **Department:** `_connectors`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_connectors/ZOHO_PROJECTS/main.py` (83 lines)

## Purpose

Zoho Projects connector: reads project delivery data from the Zoho Projects REST API (India region).
ZohoProjectsConnector.get_projects() lists active projects. get_tasks_by_owner(project_id, owner_id)
lists a user's tasks in a project. get_timelogs(project_id, owner_id, from_date, to_date) returns that
user's task time logs (dates MM-dd-yyyy). get_task_summary(project_id, owner_id) computes total,
completed (status "Closed"), overdue (not closed and end date in the past), completion_rate and
on_time_rate as percentages from those tasks. health_check() only returns status ok; it does not
call Zoho. All HTTP goes through velaris.agents.ZOHO_CONNECTOR.ZohoConnector.get, using the portal id
from config["portal_id"] or the ZOHO_PORTAL_ID environment variable.
State: keeps none; credentials live in the Zoho connector. Failure: errors from the connector
propagate; a missing key in the response yields an empty list. The config argument is optional
(None means an empty dict; the portal id then comes from ZOHO_PORTAL_ID).

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
- **tests:** `velaris/tests/test_agents_coverage_a.py`
