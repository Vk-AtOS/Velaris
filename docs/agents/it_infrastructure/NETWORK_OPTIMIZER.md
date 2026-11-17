# NETWORK_OPTIMIZER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/NETWORK_OPTIMIZER/main.py` (84 lines)

## Purpose

NETWORK_OPTIMIZER: best path through a declared network.

The caller declares links between named nodes with their measured latency and
packet-loss rate. best_path() runs Dijkstra's algorithm over the links that are
up, with each link costing its expected latency once lost packets are resent:

    cost = latency_ms / (1 - loss)

It plans over what it is told. It sends no probes, opens no sockets and changes
no routing table; the measurements are the caller's.

## Class `NETWORK_OPTIMIZERAgent`

- `__init__(name)`
- `health_check()`
- `set_link(a, b, latency_ms, loss, up)` — Declare or update the (two-way) link between a and b.
- `remove_link(a, b)`
- `best_path(src, dst)`
- `links()`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer8_gro.py`
