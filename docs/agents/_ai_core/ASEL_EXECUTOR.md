# ASEL_EXECUTOR

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ASEL_EXECUTOR/main.py` (80 lines)

## Purpose

ASEL executor: runs the steps of a plan in dependency order through caller-supplied handlers.

`handlers` maps a handler name to a Python callable taking the step. A step
runs only when every step it depends on is done. It is blocked (and everything
after it skipped) when it has no handler or needs an approval that was not
given; a handler that raises marks the step failed, and the run carries on with
whatever does not depend on it. The executor never invents a handler and never
retries. Each run is journalled.
State (last 50 runs): <VELARIS_DATA>/agents/ASEL_EXECUTOR/state.json.

## Class `ASEL_EXECUTORAgent`

- `__init__(name)`
- `health_check()`
- `execute(plan, handlers, approved)` — plan: list (or planner/router result) of {"id", "depends_on"?, "handler"|"action", "requires_approval"?}.
- `get_run(run_id)` — A journalled run by id, or the most recent one.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.graph`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/ASEL_EXECUTOR/state.json`

## Called by

- **other agents:** `ASEL`, `ASEL_EVALUATOR`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_asel.py`, `velaris/tests/test_layer13_asel.py`
