# AAE_RUNTIME

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/AAE_RUNTIME/main.py` (166 lines)

## Purpose

AAE runtime: runs one approved action, once, and keeps a record of it.

An action is {"id", "type", "params"?}. run() asks AAE_POLICY first: a denied
action does not run. One that needs approval goes through two people
(velaris.core.access gives who the current caller is):

  1. run(action) by the requester records a request (requested_by = the caller,
     and a digest of the action) and returns needs_approval. With no caller,
     nothing is recorded and the action can never be approved as it stands.
  2. run(action, approved_by=...) by someone else runs it. `approved_by` must be
     the caller's own id; the requester cannot approve their own request; the
     action must be exactly the one requested (same digest); and there must be
     a recorded request.
The handler for the action type is a Python callable registered by the caller.
An action id that already completed is not run again; the recorded result is
returned (`replayed`). Every attempt goes to the journal and to the hash-chained
trace in velaris.intel.trace (action type and outcome, not the parameters).
State (journal by action id): <VELARIS_DATA>/agents/AAE_RUNTIME/state.json.

## Class `AAE_RUNTIMEAgent`

- `__init__(policy)`
- `health_check()`
- `register(action_type, handler)`
- `run(action, approved_by)`
- `clear_stuck(action_id)` — Operator action (security or governance admin, traced): forget an action id left 'in_progress' by a crash.
- `history(action_id)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.AAE_POLICY.main`
- `velaris.core.access`
- `velaris.intel`

## State and configuration

- state file: `<VELARIS_DATA>/agents/AAE_RUNTIME/state.json`

## Called by

- **other agents:** `ADAPTIVE_ACTION_ENGINE`
- **platform modules:** `velaris/intel/approvals.py`
- **tests:** `velaris/tests/test_aicore_a_aae.py`, `velaris/tests/test_approval_audit.py`, `velaris/tests/test_kan104_operator_clear.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_layer25_aae.py`
