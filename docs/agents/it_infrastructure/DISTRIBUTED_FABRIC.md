# DISTRIBUTED_FABRIC

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/DISTRIBUTED_FABRIC/main.py` (83 lines)

## Purpose

DISTRIBUTED_FABRIC: which node owns which key (consistent hashing).

Nodes join a hash ring at `vnodes` points each. locate(key) walks clockwise from
the key's hash and returns the first `replicas` distinct nodes, so:

  - every caller, on any machine with the same membership, gets the same answer
  - a node joining or leaving moves only about 1/N of the keys

This is the placement map only. It moves no data and talks to no node; whoever
stores the data asks it where things go. Membership survives restarts.

## Class `DISTRIBUTED_FABRICAgent`

- `__init__(name)`
- `health_check()`
- `join(node, vnodes)`
- `leave(node)`
- `locate(key, replicas)` — The nodes that own `key`, primary first. Fewer than `replicas` only if the ring is smaller.
- `distribution(keys)` — How many of `keys` each node is primary for.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer9_compute.py`
