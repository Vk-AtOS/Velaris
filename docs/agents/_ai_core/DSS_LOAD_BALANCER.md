# DSS_LOAD_BALANCER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/DSS_LOAD_BALANCER/main.py` (54 lines)

## Purpose

DSS load balancer: weighted least-load node selection with health checks and shedding.

A request goes to the node with the fewest active requests per unit of weight.
Down nodes are never chosen; degraded nodes only when no healthy node has room;
a node at or over its capacity is skipped. When nothing has room the request is
shed (status "shed") instead of being piled onto a full node.

## Class `DSS_LOAD_BALANCERAgent`

- `__init__(name)`
- `health_check()`
- `pick(nodes, now, exclude)` — Choose a node for one request. Returns the choice and why the others were skipped.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agents.DSS_MONITOR.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `DSS_CLUSTER_MANAGER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_dss.py`, `velaris/tests/test_layer10_dss.py`
