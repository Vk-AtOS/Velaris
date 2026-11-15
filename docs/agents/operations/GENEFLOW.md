# GENEFLOW

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/GENEFLOW/main.py` (47 lines)

## Purpose

_No module docstring yet._

## Class `GeneFlowAgent`

- `__init__(config)`
- `health_check()`
- `compute_diff(old, new)` — Return added, removed, changed keys.
- `apply_migration(base, changes)` — Apply changes to a dict for migration.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_geneflow.py`, `velaris/tests/test_kan106_business_agents.py`
