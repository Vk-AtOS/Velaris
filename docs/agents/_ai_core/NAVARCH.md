# NAVARCH

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/NAVARCH/main.py` (65 lines)

## Purpose

Navarch: finds the cheapest path through a weighted graph and passes step lists through.

compute_path(graph, start, goal) runs Dijkstra over {node: {neighbour: weight}} and returns {"path": [...], "cost": n},
or None when the goal cannot be reached. Weights are assumed non-negative and are not checked. sequence_steps(steps)
only logs the list and returns it unchanged (a stub). health_check() returns {"agent", "status": "ok", "version"}.
Keeps no state. A malformed graph (a non-dict neighbour map) raises from the underlying dict or arithmetic.

## Class `NavarchAgent`

- `__init__(config)`
- `health_check()`
- `compute_path(graph, start, goal)` — Dijkstra-style shortest path.
- `sequence_steps(steps)` — Simple passthrough but logs sequencing.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_navarch.py`
