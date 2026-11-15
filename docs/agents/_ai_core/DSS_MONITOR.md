# DSS_MONITOR

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/DSS_MONITOR/main.py` (62 lines)

## Purpose

DSS monitor: classifies each node as healthy, degraded or down.

down      no heartbeat yet, the last one is older than `timeout_s`, or it lies more than `clock_skew_s` in the future
degraded  alive, but cpu, memory or error rate is over its limit
healthy   everything else
Works on a node list passed in, or on the DSS_CLUSTER_MANAGER registry.

## Class `DSS_MONITORAgent`

- `__init__(name, timeout_s, limits, clock_skew_s)`
- `health_check()`
- `assess(nodes, now)` — Returns per-node state with reasons, plus the healthy / degraded / down name lists.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agents.DSS_CLUSTER_MANAGER.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `DSS_CLUSTER_MANAGER`, `DSS_FAILOVER`, `DSS_LOAD_BALANCER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_dss.py`, `velaris/tests/test_layer10_dss.py`, `velaris/tests/test_r3_dss.py`
