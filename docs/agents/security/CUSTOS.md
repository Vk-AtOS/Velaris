# CUSTOS

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/CUSTOS/main.py` (32 lines)

## Purpose

_No module docstring yet._

## Class `CustosAgent`

- `__init__(config)`
- `health_check()`
- `define_role(role, perms)`
- `assign_permission(role, permission)`
- `check_access(role, action)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `PRIME`
- **platform modules:** none found
- **tests:** `velaris/tests/test_custos.py`, `velaris/tests/test_engine.py`, `velaris/tests/test_system_integration.py`
