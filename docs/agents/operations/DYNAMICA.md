# DYNAMICA

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/DYNAMICA/main.py` (57 lines)

## Purpose

Dynamica: simple step-wise system evolution (a simulation stub).
DynamicaAgent.evolve_linear(initial, delta) returns config "steps" values (default 5) rising by delta.
evolve_multi(initial, update) returns the initial dict plus the results of applying the update
function to a copy of the previous state, steps in total. system_state(name) returns a descriptive
dict with the name and step count. health_check() returns status ok and version.
State: keeps none beyond config. Failure: exceptions from the update function propagate; with steps
of 0 or less evolve_linear returns [] while evolve_multi still returns the initial state.

## Class `DynamicaAgent`

- `__init__(config)`
- `health_check()`
- `evolve_linear(initial, delta)` — Increase value by delta each step.
- `evolve_multi(initial, update)` — Apply multi-variable updates across steps.
- `system_state(name)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dynamica.py`
