# DSS_REPLICATION

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/DSS_REPLICATION/main.py` (78 lines)

## Purpose

DSS replication: decides which nodes hold the copies of a key, and audits the result.

Placement uses rendezvous (highest-random-weight) hashing, so adding or removing
a node only moves the keys that touched it, and spreads copies across zones
before putting two in the same zone. The audit compares placements with the set
of live nodes and returns the keys that are lost or short of copies, with the
node each missing copy should be rebuilt on. It plans; it does not move data.

## Class `DSS_REPLICATIONAgent`

- `__init__(name)`
- `health_check()`
- `place(key, nodes, factor, exclude)` — Pick up to `factor` nodes for `key`. Status is under_replicated if there are too few nodes.
- `audit(placements, live_nodes, factor)` — Compare {key: [nodes]} with the live nodes; return lost keys and a repair plan.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_dss.py`, `velaris/tests/test_layer10_dss.py`, `velaris/tests/test_r3_dss.py`
