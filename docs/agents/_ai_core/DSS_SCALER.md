# DSS_SCALER

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/DSS_SCALER/main.py` (67 lines)

## Purpose

DSS scaler: decides how many nodes the cluster should run (target tracking).

desired = ceil(current * metric / target), clamped to [min_nodes, max_nodes].
Nothing changes while the metric is within `tolerance` of the target or within
`cooldown_s` of the last change, and the cluster shrinks by one node at a time.
The agent returns the decision; starting or stopping machines is the caller's job.
State (time of the last change per cluster): <VELARIS_DATA>/agents/DSS_SCALER/state.json.

## Class `DSS_SCALERAgent`

- `__init__(name, cooldown_s, tolerance)`
- `health_check()`
- `decide(current, metric, target, min_nodes, max_nodes, now, cluster)` — `metric` and `target` are in the same unit (e.g. average CPU, queue length per node). The cooldown is kept

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/DSS_SCALER/state.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_dss.py`, `velaris/tests/test_layer10_dss.py`, `velaris/tests/test_r3_dss.py`
