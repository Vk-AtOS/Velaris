# CLBPP_OVERLOAD_MONITOR

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CLBPP_OVERLOAD_MONITOR/main.py` (64 lines)

## Purpose

CLBPP overload monitor: flags a worker whose utilisation stays high.

A worker becomes overloaded after `sustain` consecutive samples at or above
`high`, and returns to normal only when a sample drops below `low`, so one
spike or one dip does not flip the flag. Keeps the last `window` samples per worker.
State: <VELARIS_DATA>/agents/CLBPP_OVERLOAD_MONITOR/state.json.

## Class `CLBPP_OVERLOAD_MONITORAgent`

- `__init__(name, high, low, sustain, window)`
- `health_check()`
- `record(worker, utilisation, now)` — Add one utilisation sample (load / capacity; above 1 means over capacity).
- `status(worker)` — One worker's state, or every worker's plus the list of overloaded ones.
- `history(worker)` — Utilisation samples for one worker, oldest first (input for CLBPP_PREDICTIVE_BALANCER).

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CLBPP_OVERLOAD_MONITOR/state.json`

## Called by

- **other agents:** `CLBPP_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_clbpp.py`, `velaris/tests/test_layer11_clbpp.py`
