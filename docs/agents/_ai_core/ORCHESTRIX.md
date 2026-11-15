# ORCHESTRIX

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ORCHESTRIX/main.py` (69 lines)

## Purpose

Orchestrix: orders tasks by their dependencies and groups them into parallel batches.
OrchestrixAgent.resolve_dependencies(tasks) takes {task: [dependencies]} and returns a topological
order (depth-first); a cycle raises Exception("Circular dependency detected: <task>"). A dependency
missing from the keys is included in the order as a task with no dependencies.
parallel_groups(order, tasks) returns batches where each task sits one level after its deepest
dependency, so every dependency is in an earlier batch. health_check() returns status ok and version.
State: keeps no state between calls. Failure: bad input types raise the usual Python errors
(TypeError, AttributeError); there is no other validation.

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
