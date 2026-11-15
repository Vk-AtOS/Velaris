# OPERATUS

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/OPERATUS/main.py` (62 lines)

## Purpose

_No module docstring yet._

## Class `OperatusAgent`

- `__init__(config)`
- `health_check()`
- `register(step, handler)` — The code that runs a step of this name.
- `execute_workflow(steps)` — Run workflow steps in order with their registered handlers. A step is "done" only if its handler ran
- `validate_inputs(inputs, required)` — Validate that required keys exist in input dictionary.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_operatus.py`
