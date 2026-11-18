# DYNAMICA

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/DYNAMICA/main.py` (55 lines)

## Purpose

Dynamica: steps a value, or a dict of values, forward a fixed number of times.

DynamicaAgent(config; "steps" default 5, "version"): health_check(); evolve_linear(initial, delta) returns
[initial + i * delta] for each step; evolve_multi(initial, update) returns the list of states, starting with a copy of
initial and applying update(state) steps - 1 times (states are deep-copied, so the caller's dict and earlier results are
never changed); system_state(name) returns {name, steps, description}.
State: keeps none between calls. Failure: no input validation; non-numeric values raise TypeError and an exception from
the update function propagates.

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
- **tests:** `velaris/tests/test_dynamica.py`, `velaris/tests/test_kan86_operations.py`
