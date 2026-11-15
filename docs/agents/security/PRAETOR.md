# PRAETOR

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/PRAETOR/main.py` (48 lines)

## Purpose

Praetor: z-score anomaly detector for a series of numbers.

detect_anomaly(values) is True when the last value lies more than config["threshold"] (default
3.0) standard deviations from the mean of the values before it. Fewer than 3 values give False;
a flat baseline (zero deviation) flags any different latest value. A statistical rule, not a
learned model. Keeps no state. Non-numeric values raise.

## Class `PraetorAgent`

- `__init__(config)`
- `health_check()`
- `detect_anomaly(values)` — True when the latest value is more than `threshold` standard deviations

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `PRIME`
- **platform modules:** none found
- **tests:** `velaris/tests/test_praetor.py`, `velaris/tests/test_system_integration.py`
