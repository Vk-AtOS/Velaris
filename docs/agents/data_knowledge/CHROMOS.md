# CHROMOS

- **Department:** `data_knowledge`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/data_knowledge/CHROMOS/main.py` (50 lines)

## Purpose

_No module docstring yet._

## Class `ChromosAgent`

- `__init__(config)`
- `health_check()`
- `normalize_schema(schema_dict)` — Sort keys, remove whitespace, and produce deterministic ordering.
- `schema_hash(normalized_schema)` — SHA-256 hash of schema.
- `store_schema(key, schema_dict)`
- `compare_schema(key, new_schema)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_chromos.py`
