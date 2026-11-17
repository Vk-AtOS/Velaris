# RECURSIVE_GOAL_PLANNER

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/RECURSIVE_GOAL_PLANNER/main.py` (139 lines)

## Purpose

RECURSIVE_GOAL_PLANNER: flattens a nested goal into a dependency-ordered task list.

recurse(plan) takes {"goal": "...", "subgoals": [{"id", "title", "depends_on": [...], "subgoals": [...]}]}
(nesting to any depth up to MAX_DEPTH), or HYPER_REASONER's output (refused
when the graph was not validated), or {"steps": [...]} where a step without
"depends_on" follows the one before it. Leaves become tasks. A dependency on a
subgoal that has children means "after all of that subgoal's tasks". The
tasks are then ordered; an unknown dependency or a cycle makes the plan
invalid and is reported, never silently dropped. A goal with no subgoals
becomes a single task.

decompose(goal, llm) is the only part that uses a model: it asks for subgoals
as JSON and passes the reply through the same validation; with no model it
returns not_configured.

## Class `PlanError`


## Class `RecursiveGoalPlanner`

- `__init__(name)`
- `health_check()`
- `recurse(plan)`
- `decompose(goal, llm)` — Ask a model for subgoals of `goal`, then validate and order them with recurse().

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.models`
- `velaris.agentkit.results`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `AIIE_KERNEL`, `HYPER_REASONER`, `SELF_DIRECTED_TASKER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_AI_IE_layer.py`, `velaris/tests/test_aicore_b_aiie.py`, `velaris/tests/test_engine.py`
