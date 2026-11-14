# ARGUS

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/ARGUS/main.py` (49 lines)

## Purpose

_No module docstring yet._

## Class `ArgusAgent`

- `__init__(config)`
- `health_check()`
- `update_heartbeat(source)`
- `is_missing_heartbeat(source)`
- `update_signature(source, version)`
- `signature_changed(source, new_version)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_argus.py`
