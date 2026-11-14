# VELOCITY_LOOP

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/VELOCITY_LOOP/main.py` (89 lines)

## Purpose

VELOCITY_LOOP: where one piece of work lost its time.

accelerate(task) takes a task with the stages it has passed through:

    {"id": "T-17", "stages": [{"name": "review", "entered": "2026-11-02T09:00",
                               "left": "2026-11-04T17:00", "active_hours": 3}, ...]}

and computes, from the timestamps:
  hours in each stage and its share of the lead time,
  the bottleneck (the stage that held the task longest),
  flow efficiency = active hours / lead time, when every stage reports active_hours.

It then proposes looking at the bottleneck first. That is a suggestion for a
person: `final` stays "ready_for_approval" and the agent changes nothing. It does
not speed anything up by itself, and it measures elapsed clock time, not working hours.

## Class `VelocityLoop`

- `__init__(name)`
- `health_check()`
- `accelerate(task)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `AIIE_KERNEL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_AI_IE_layer.py`, `velaris/tests/test_dept_operations_stubs.py`
