# DSS_FAILOVER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/DSS_FAILOVER/main.py` (63 lines)

## Purpose

DSS failover: keeps one primary node and promotes a standby when it goes down.

The primary is replaced only when DSS_MONITOR reports it down (a degraded
primary stays, to avoid flapping). The successor is chosen deterministically:
healthy before degraded, then highest priority, then lowest name. Every change
increments a term number so stale primaries can be recognised (a call that changes nothing, such as no node being
alive while there is no primary, does not).
State: <VELARIS_DATA>/agents/DSS_FAILOVER/state.json.

## Class `DSS_FAILOVERAgent`

- `__init__(name)`
- `health_check()`
- `status()`
- `evaluate(nodes, now)` — Check the primary against current health and promote a standby if it is down.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.DSS_MONITOR.main`

## State and configuration

- state file: `<VELARIS_DATA>/agents/DSS_FAILOVER/state.json`

## Called by

- **other agents:** `DSS_CLUSTER_MANAGER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_dss.py`, `velaris/tests/test_layer10_dss.py`, `velaris/tests/test_r3_dss.py`
