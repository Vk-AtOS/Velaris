# PRAETOR

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/PRAETOR/main.py` (41 lines)

## Purpose

_No module docstring yet._

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
