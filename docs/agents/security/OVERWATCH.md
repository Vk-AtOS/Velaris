# OVERWATCH

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/OVERWATCH/main.py` (58 lines)

## Purpose

_No module docstring yet._

## Class `OverwatchAgent`

- `__init__(config)`
- `health_check()`
- `record_snapshot(key, metrics)` — Record reference snapshot.
- `detect_drift(key, new_metrics, tolerance)` — Compare new metrics to baseline.
- `summarize_change(key, new_metrics)` — Returns dict showing metric deltas from baseline.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_overwatch.py`
