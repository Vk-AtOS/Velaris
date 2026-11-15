# HELIX

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/HELIX/main.py` (50 lines)

## Purpose

Helix: stores and verifies SHA-256 signatures of "genome" data.
HelixAgent.generate_signature(data) returns the SHA-256 hex digest of the JSON of data (sorted keys).
store_genome(key, data) stores that signature under key and returns it. verify_genome(key, data)
returns True when the signature of data equals the stored one, False for an unknown key or a mismatch.
Only the hash is kept, not the data. It is a plain integrity check with no secret key, so it does
not prove who produced the data.
State: in-memory dict only, nothing persisted. Failure: data that is not JSON serializable raises
TypeError.

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
