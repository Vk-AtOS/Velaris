# SENTINELDNA

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/SENTINELDNA/main.py` (41 lines)

## Purpose

_No module docstring yet._

## Class `SentinelDNAAgent`

- `__init__(config)`
- `health_check()`
- `compute_hash(data)`
- `set_baseline(key, data)`
- `drift_detected(key, new_data)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_sentineldna.py`
