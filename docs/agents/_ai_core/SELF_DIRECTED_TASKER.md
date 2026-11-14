# SELF_DIRECTED_TASKER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/SELF_DIRECTED_TASKER/main.py` (94 lines)

## Purpose

SELF_DIRECTED_TASKER: works through an ordered task list, releasing tasks as their dependencies finish.

prepare(expanded) takes RECURSIVE_GOAL_PLANNER's output and says which tasks
can start now and which are blocked by what; it stores nothing.

start(expanded) stores the plan as a queue under this agent's state directory
and returns a plan_id. next_tasks(plan_id) lists the tasks that are ready,
complete(plan_id, task_id) marks one done (only a ready task can be completed)
and returns what that released. The queue survives a restart. The agent
tracks state; it does not execute the tasks itself.

## Class `SelfDirectedTasker`

- `__init__(name)`
- `health_check()`
- `prepare(expanded)` — Which tasks are ready and which are blocked. task_ready is True when at least one can start.
- `start(expanded)` — Store the plan as a queue. Returns plan_id and the tasks that can start.
- `next_tasks(plan_id)`
- `complete(plan_id, task_id)` — Mark a ready task done. Returns the tasks this released.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/SELF_DIRECTED_TASKER/queues.json`

## Called by

- **other agents:** `AIIE_KERNEL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_AI_IE_layer.py`, `velaris/tests/test_aicore_b_aiie.py`
