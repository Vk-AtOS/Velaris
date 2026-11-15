# ORCHESTRIX

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ORCHESTRIX/main.py` (64 lines)

## Purpose

_No module docstring yet._

## Class `OrchestrixAgent`

- `__init__(config)`
- `health_check()`
- `resolve_dependencies(tasks)` — Topological sort of tasks with dependencies.
- `parallel_groups(order, tasks)` — Group tasks into parallel-safe batches.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CONVERGENCE_BRIDGE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_eof.py`, `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_kan106_intake_guards.py`, `velaris/tests/test_layer31_eof.py`, `velaris/tests/test_loader_and_fail_closed.py`, `velaris/tests/test_orchestrix.py`
