# POLARIS

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/POLARIS/main.py` (51 lines)

## Purpose

_No module docstring yet._

## Class `PolarisAgent`

- `__init__(config)`
- `health_check()`
- `compute_score(strategy)` — Compute weighted long-term alignment score.
- `rank_long_term(strategies)`
- `best_trajectory(strategies)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_polaris.py`
