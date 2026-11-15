# MEMORY_MESH

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/MEMORY_MESH/main.py` (113 lines)

## Purpose

MEMORY_MESH: which memory node serves which scope, and recall across several scopes.

A node is anything that holds memories (a tenant's store, a site, a device). It
registers the scopes it serves and sends heartbeats. route(scope) lists the
nodes that serve that scope and have been heard from within `ttl_s`.

recall_across() asks the long-term store (velaris.intel.memory) for the best
memories in each scope the caller names and merges them by score. It never
widens the search: a scope that is not in the list is not read, so one tenant's
memories cannot surface in another's answer.

The registry is on disk. (velaris/memory/mesh.py is an unrelated in-process
dictionary and is not used here.)

## Class `MemoryAgentBase`

Node registry shared by mesh-like memory components. Constructible with no arguments.

- `__init__(name)`
- `health_check()`
- `register_node(node_id, meta, now)` — Add or replace a node. meta["scopes"] (a list of scope names) says what it serves.
- `nodes()` — {node_id: meta} for every registered node.
- `heartbeat(node_id, now)`
- `remove_node(node_id)`
- `route(scope, ttl_s, now)` — Live nodes serving `scope`, most recently heard from first.
- `recall_across(query, scopes, k)` — The k best memories for `query` over exactly the listed scopes.

## Class `MEMORY_MESHAgent`

- `__init__()`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`
- `velaris.intel.memory`

## State and configuration

- state file: `<VELARIS_DATA>/agents/MEMORY_MESH/nodes.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_data_knowledge_stubs.py`, `velaris/tests/test_memory_substrate.py`
