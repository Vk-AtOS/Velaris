# OPERATUS

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/OPERATUS/main.py` (72 lines)

## Purpose

Operatus: runs a named workflow by calling the handler registered for each step in order.

OperatusAgent(config): health_check(); register(step, handler) maps a step name to a
callable; execute_workflow(steps) calls each handler with no arguments and returns
{"steps": [...], "status"}; validate_inputs(inputs, required) is True when every required
key is present.
Step results are "done" (with output), "not_run" (no handler; overall status becomes
"incomplete" and later steps still run) or "failed" (handler raised; status "failed" and
the workflow stops).
State: in memory only (self.handlers), lost on restart.
Failure: register raises ValueError for a non-string step or non-callable handler;
handler exceptions are caught and reported, not raised.

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
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_operatus.py`
