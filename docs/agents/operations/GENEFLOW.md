# GENEFLOW

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/GENEFLOW/main.py` (50 lines)

## Purpose

Geneflow: diffs two dicts and applies the diff as a migration.

compute_diff(old, new) returns {added, removed, changed, values}, where values holds the new
value of every added or changed key. apply_migration(base, changes) returns a copy of base with
removed keys dropped and added/changed keys set from the diff's values (or from a dict-form
"added"/"changed"); it raises ValueError when no new value can be found for a key. Top-level
keys only, no nested diff. Keeps no state; the input dict is not modified.

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
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_geneflow.py`, `velaris/tests/test_kan106_business_agents.py`
