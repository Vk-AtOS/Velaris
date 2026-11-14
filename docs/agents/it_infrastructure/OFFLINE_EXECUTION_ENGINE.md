# OFFLINE_EXECUTION_ENGINE

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/OFFLINE_EXECUTION_ENGINE/main.py` (62 lines)

## Purpose

OFFLINE_EXECUTION_ENGINE: a durable, replay-safe journal of local command runs.

execute(task) runs task["argv"] through OFFLINE_SANDBOX (allow-listed commands
only, no shell, temporary directory, scrubbed environment, timeout, capped
output) and writes the outcome to a journal on disk. A task that carries an
"id" runs at most once: asking again returns the recorded result instead of
running it a second time, so a retry after a crash or a lost reply is safe.

The containment is OFFLINE_SANDBOX's: process isolation, not a security sandbox.

## Class `OfflineExecutionEngine`

- `__init__(name)`
- `health_check()`
- `execute(task)`
- `get(task_id)`
- `history(n)`

## Depends on

- `velaris.agentkit`
- `velaris.agents.OFFLINE_SANDBOX`

## State and configuration

- state file: `<VELARIS_DATA>/agents/OFFLINE_EXECUTION_ENGINE/journal.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer7_offline.py`
