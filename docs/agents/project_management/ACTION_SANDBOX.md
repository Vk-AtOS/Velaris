# ACTION_SANDBOX

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/ACTION_SANDBOX/main.py` (63 lines)

## Purpose

ACTION_SANDBOX: apply an action to a COPY of some state and report what would change.

sandbox_execute(action, state=None) understands four operations on a flat mapping:

  {"op": "set", "key": k, "value": v}          {"op": "delete", "key": k}
  {"op": "increment", "key": k, "by": n}       {"op": "append", "key": k, "value": v}

It returns the before and after of the key, and the whole state as it would be.
The caller's state object is never modified and nothing outside this call is
touched: `result` is always "simulated". An action without a known `op` is
returned as `unsupported` with no changes, never pretended to have run.

## Class `ACTION_SANDBOXAgent`

- `__init__()`
- `health_check()`
- `sandbox_execute(action, state)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_project_management_stubs.py`, `velaris/tests/test_governance_kernel.py`
