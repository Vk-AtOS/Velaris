# DSS_CLUSTER_MANAGER

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/DSS_CLUSTER_MANAGER/main.py` (74 lines)

## Purpose

DSS cluster manager: the registry of worker nodes for the DSS family.

Keeps which nodes exist, their weight, zone and failover priority, and the last
heartbeat and metrics each one reported. DSS_MONITOR, DSS_LOAD_BALANCER and
DSS_FAILOVER read this registry when they are not handed a node list.
State: <VELARIS_DATA>/agents/DSS_CLUSTER_MANAGER/state.json.

## Class `DSS_CLUSTER_MANAGERAgent`

- `__init__(name)`
- `health_check()`
- `register_node(node, weight, zone, priority, now)` — Add a node or update its weight, zone and priority. Heartbeat data is kept.
- `deregister_node(node)`
- `heartbeat(node, metrics, now)` — Record that a registered node is alive, with optional numeric metrics.
- `nodes()` — All registered nodes, sorted by name.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/DSS_CLUSTER_MANAGER/state.json`

## Called by

- **other agents:** `DSS_MONITOR`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_dss.py`, `velaris/tests/test_layer10_dss.py`
