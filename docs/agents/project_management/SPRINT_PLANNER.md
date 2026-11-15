# SPRINT_PLANNER

- **Department:** `project_management`
- **Status (static inventory):** `real`
- **Source:** `departments/project_management/SPRINT_PLANNER/main.py` (187 lines)

## Purpose

Sprint planner: creates sprints, holds their tasks and story points, and reports velocity.

create_sprint(project_id, sprint_number, name, start_date, velocity_target) sets the end date from the sprint_weeks config
(default 2); a bad ISO date raises ValueError and a duplicate number returns {"error": ...}. add_task(sprint_id, task_id,
title, assignee, story_points) rejects negative, non-finite or non-numeric points with {"error": ...}. update_task_status
accepts todo, in_progress, review, done. get_sprint_board(id) groups tasks by status with total and completed points and a
velocity percentage ({"error": "sprint_not_found"} if unknown). close_sprint(id) marks it completed and returns points done.
project_velocity_trend(project) compares target and achieved for completed sprints. It does not sync with Zoho Projects.
Unknown ids are not checked in add_task, update_task_status or close_sprint. No caller check is made.
State: sqlite at <VELARIS_DATA>/agents/SPRINT_PLANNER/sprints.db.

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

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_no_state_in_source_tree.py`
