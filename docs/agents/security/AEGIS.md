# AEGIS

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/AEGIS/main.py` (46 lines)

## Purpose

_No module docstring yet._

## Class `AegisAgent`

- `__init__(config)`
- `health_check()`
- `record_event(source)`
- `is_rate_limited(source)`
- `adjust_threat(source, delta)`
- `get_threat(source)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aegis.py`
