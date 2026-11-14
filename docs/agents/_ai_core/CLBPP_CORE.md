# CLBPP_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CLBPP_CORE/main.py` (97 lines)

## Purpose

CLBPP core: the workload ledger for a pool of workers (people, queues or agents).

Keeps each worker's capacity and the tasks it currently holds. submit() places
new tasks through CLBPP_DISTRIBUTOR against the current loads, complete() frees
them, and every change feeds a utilisation sample to CLBPP_OVERLOAD_MONITOR.
rebalance_plan() asks CLBPP_PREDICTIVE_BALANCER what to move before anyone overloads.
State: <VELARIS_DATA>/agents/CLBPP_CORE/state.json.

## Class `CLBPP_COREAgent`

- `__init__(name)`
- `health_check()`
- `register_worker(worker, capacity, skills)`
- `submit(tasks, now)` — Place tasks on registered workers. Ids already in the ledger are rejected, not duplicated.
- `complete(task_id, now)`
- `status()`
- `rebalance_plan(threshold)` — Forecast from the monitor's samples and return proposed transfers.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.CLBPP_DISTRIBUTOR.main`
- `velaris.agents.CLBPP_OVERLOAD_MONITOR.main`
- `velaris.agents.CLBPP_PREDICTIVE_BALANCER.main`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CLBPP_CORE/state.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_clbpp.py`, `velaris/tests/test_layer11_clbpp.py`
