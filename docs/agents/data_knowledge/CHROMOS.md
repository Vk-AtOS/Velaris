# CHROMOS

- **Department:** `data_knowledge`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/data_knowledge/CHROMOS/main.py` (61 lines)

## Purpose

Chromos: detects schema changes by hashing a canonical JSON form of each schema.

ChromosAgent(config): health_check(); normalize_schema(dict) returns JSON with sorted
keys; schema_hash(normalized) returns its SHA-256 hex; store_schema(key, dict) records
the hash under key and returns it; compare_schema(key, new_schema) returns True when the
new hash differs from the stored one.
State: in memory only (self.schemas, hashes not schemas), lost on restart.
Failure: compare_schema returns False for an unknown key (indistinguishable from
unchanged); a schema that json cannot serialise raises TypeError.

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
