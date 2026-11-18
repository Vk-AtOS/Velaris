# ASEL_EXECUTOR

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/ASEL_EXECUTOR/main.py` (98 lines)

## Purpose

ASEL executor: runs the steps of a plan in dependency order through caller-supplied handlers.

`handlers` maps a handler name to a Python callable taking the step. A step
runs only when every step it depends on is done. It is blocked (and everything
after it skipped) when it has no handler or needs an approval that was not
given; a handler that raises marks the step failed, and the run carries on with
whatever does not depend on it. The executor never invents a handler and never
retries. Each run is journalled.

A step with "requires_approval" runs only with PROOF: `approved` maps its id to {"trace_hash": ...}, the trace
entry of PRIME's allow decision for that step or of a person's approval (VCAS_CORE), whose task_digest is the
digest of this very step (velaris.agentkit.aicore_b_authz.approval_proven), made by the current caller. The
caller's own say-so ("approved": ["s1"]) is not an approval. Each hash is spent once.
State (last 50 runs): <VELARIS_DATA>/agents/ASEL_EXECUTOR/state.json.

## Class `ASEL_EXECUTORAgent`

- `__init__(name)`
- `health_check()`
- `execute(plan, handlers, approved)` — plan: list (or planner/router result) of {"id", "depends_on"?, "handler"|"action", "requires_approval"?}.
- `get_run(run_id)` — A journalled run by id, or the most recent one.

## Depends on

- `velaris.agentkit.aicore_b_authz`
- `velaris.agentkit.checks`
- `velaris.agentkit.graph`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/ASEL_EXECUTOR/state.json`

## Called by

- **other agents:** `ASEL`, `ASEL_EVALUATOR`, `VCAS_AUTOPILOT`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_asel.py`, `velaris/tests/test_layer13_asel.py`
