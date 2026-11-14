# OPERATUS

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/OPERATUS/main.py` (41 lines)

## Purpose

_No module docstring yet._

## Class `OperatusAgent`

- `__init__(config)`
- `health_check()`
- `execute_workflow(steps)` — Execute workflow steps in order. Returns execution report.
- `validate_inputs(inputs, required)` — Validate that required keys exist in input dictionary.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_operatus.py`
