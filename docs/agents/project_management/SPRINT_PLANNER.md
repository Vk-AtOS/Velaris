# SPRINT_PLANNER

- **Department:** `project_management`
- **Status (static inventory):** `real`
- **Source:** `departments/project_management/SPRINT_PLANNER/main.py` (178 lines)

## Purpose

_No module docstring yet._

## Class `SprintPlanner`

Scrum/Kanban sprint management: create sprints, assign tasks, track velocity.
Integrates with ZOHO_PROJECTS for task sync when configured.

- `__init__(config)`
- `health_check()`
- `create_sprint(project_id, sprint_number, name, start_date, velocity_target)`
- `add_task(sprint_id, task_id, title, assignee, story_points)`
- `update_task_status(item_id, status)` — status: todo | in_progress | review | done
- `get_sprint_board(sprint_id)`
- `close_sprint(sprint_id)` — Mark sprint done; returns velocity achieved.
- `project_velocity_trend(project_id)`

## Depends on

- `velaris.core.sqlite_util`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_no_state_in_source_tree.py`
