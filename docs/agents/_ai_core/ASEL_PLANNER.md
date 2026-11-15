# ASEL_PLANNER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ASEL_PLANNER/main.py` (52 lines)

## Purpose

ASEL planner: schedules a set of dependent tasks (critical path method).

Each task is {"id", "duration"?, "depends_on"?, ...}. The planner orders them,
computes earliest start and finish, slack and the critical path, and returns
the total duration. Unknown or circular dependencies make the plan invalid.
Resources are not modelled: tasks with no dependency between them are assumed
to run in parallel.

## Class `ASEL_PLANNERAgent`

- `__init__(name)`
- `health_check()`
- `plan(tasks)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.graph`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ASEL`, `DECISION_GRAPH_ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_asel.py`, `velaris/tests/test_layer13_asel.py`
