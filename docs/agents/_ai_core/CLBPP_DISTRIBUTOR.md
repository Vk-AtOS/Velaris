# CLBPP_DISTRIBUTOR

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CLBPP_DISTRIBUTOR/main.py` (68 lines)

## Purpose

CLBPP distributor: assigns a batch of tasks to workers without overfilling anyone.

Tasks are placed largest first; each goes to the worker that has the skill, has
room, and would end up least utilised (load / capacity). A task that fits
nowhere is returned as unassigned with the reason, never squeezed in.
Deterministic greedy heuristic, not an optimal bin-packing.

## Class `CLBPP_DISTRIBUTORAgent`

- `__init__(name)`
- `health_check()`
- `distribute(tasks, workers)` — tasks: [{"id", "effort", "skill"?}]; workers: [{"name", "capacity", "load"?, "skills"?}].

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CLBPP_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_clbpp.py`, `velaris/tests/test_layer11_clbpp.py`
