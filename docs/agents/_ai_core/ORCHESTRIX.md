# ORCHESTRIX

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ORCHESTRIX/main.py` (43 lines)

## Purpose

Orchestrix: orders tasks by their dependencies and groups them into parallel batches.
It is a thin face of velaris.agentkit.graph.order, the ONE dependency ordering of the platform (the central brain orders its
plans with it too); there is no second sort here. resolve_dependencies(tasks) takes {task: [dependencies]} and returns the order
(by level, then name). A cycle raises ValueError("Circular dependency detected: a -> b -> a") and a dependency that is not a
key of `tasks` raises ValueError("unknown dependencies: ..."): both used to be a bare Exception and a silent inclusion.
parallel_groups(order, tasks) returns the batches (levels) of the tasks in `order`; every dependency is in an earlier batch.
health_check() returns status ok and version. State: none.

## Class `OrchestrixAgent`

- `__init__(config)`
- `health_check()`
- `resolve_dependencies(tasks)` — Order of {task: [dependencies]}; ValueError on a cycle or on a dependency that is not a task.
- `parallel_groups(order, tasks)` — Batches of the tasks in `order`: each task sits one level after its deepest dependency.

## Depends on

- `velaris.agentkit.graph`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CONVERGENCE_BRIDGE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_eof.py`, `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_eof_inbox.py`, `velaris/tests/test_kan106_intake_guards.py`, `velaris/tests/test_layer31_eof.py`, `velaris/tests/test_loader_and_fail_closed.py`, `velaris/tests/test_orchestrix.py`, `velaris/tests/test_r3_eof.py`
