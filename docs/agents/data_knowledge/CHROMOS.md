# CHROMOS

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/CHROMOS/main.py` (62 lines)

## Purpose

Chromos: detects schema changes by hashing a canonical JSON form of each schema.

ChromosAgent(config): health_check(); normalize_schema(dict) returns JSON with sorted
keys; schema_hash(normalized) returns its SHA-256 hex; store_schema(key, dict) records
the hash under key and returns it; compare_schema(key, new_schema) returns True when the
new hash differs from the stored one.
State: the hashes (not the schemas) are a JsonState file under VELARIS_DATA/agents/CHROMOS, so they survive a restart.
Failure: compare_schema raises KeyError for a key that was never stored (it used to return False, which reads as "unchanged");
a schema that json cannot serialise raises TypeError.

## Class `ChromosAgent`

- `__init__(config)`
- `schemas()`
- `health_check()`
- `normalize_schema(schema_dict)` — Sort keys, remove whitespace, and produce deterministic ordering.
- `schema_hash(normalized_schema)` — SHA-256 hash of schema.
- `store_schema(key, schema_dict)`
- `compare_schema(key, new_schema)`

## Depends on

- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CHROMOS/schemas.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_chromos.py`, `velaris/tests/test_kan93_rest.py`
