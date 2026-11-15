# OVERWATCH

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/OVERWATCH/main.py` (67 lines)

## Purpose

Overwatch: compares metric snapshots against a recorded baseline to flag drift.
OverwatchAgent.record_snapshot(key, metrics) stores a copy of the metrics and returns True.
detect_drift(key, new_metrics, tolerance=0.1) returns True when any baseline metric differs by more
than the tolerance, is missing from the new data or is not a number there (NaN included), and also True
when no baseline exists for the key. summarize_change(key, new_metrics) returns the per-metric deltas from the
baseline (None for a metric that is missing or not a number in the new data), or {} for an unknown key. Absolute-difference check only.
State: baselines are in memory only, nothing persisted. Failure: non-numeric baseline values raise TypeError;
nothing is caught.

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
- **tests:** `velaris/tests/test_kan88_security_agents.py`, `velaris/tests/test_overwatch.py`
