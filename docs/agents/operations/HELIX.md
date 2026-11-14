# HELIX

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/HELIX/main.py` (41 lines)

## Purpose

_No module docstring yet._

## Class `HelixAgent`

- `__init__(config)`
- `health_check()`
- `generate_signature(data)`
- `store_genome(key, data)`
- `verify_genome(key, data)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_helix.py`, `velaris/tests/test_system_integration.py`
