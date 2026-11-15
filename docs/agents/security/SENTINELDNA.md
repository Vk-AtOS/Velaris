# SENTINELDNA

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/SENTINELDNA/main.py` (48 lines)

## Purpose

Sentinel DNA: hash baselines to detect drift in data.

compute_hash(data) is the SHA-256 of the JSON form (sorted keys; non-JSON data raises
TypeError). set_baseline(key, data) stores and returns the hash; drift_detected(key, new_data)
is True when the hash differs from the baseline, or when no baseline exists for the key.
State: a dict in memory only, so baselines are lost on restart.

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
