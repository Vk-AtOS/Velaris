# SIMULON

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/SIMULON/main.py` (53 lines)

## Purpose

Simulon: simple step-wise simulations (a stub).
SimulonAgent.run_linear(start, step) returns config "steps" values (default 5) rising by step.
run_dynamic(initial, func) returns the initial value followed by repeated applications of func,
steps values in total. scenario(name) returns a descriptive dict with the name and duration.
health_check() returns status ok and version.
State: keeps none beyond config. Failure: exceptions from func propagate; with steps of 0 or less
run_linear returns [] while run_dynamic still returns the initial value.

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
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_simulon.py`
