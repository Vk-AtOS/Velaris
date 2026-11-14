# NAVARCH

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/NAVARCH/main.py` (58 lines)

## Purpose

_No module docstring yet._

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
