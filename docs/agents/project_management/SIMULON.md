# SIMULON

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/SIMULON/main.py` (49 lines)

## Purpose

_No module docstring yet._

## Class `SimulonAgent`

- `__init__(config)`
- `health_check()`
- `run_linear(start, step)` — Simulate linear step progression.
- `run_dynamic(initial, func)` — Repeatedly apply a function to generate dynamic simulation.
- `scenario(name)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_simulon.py`
