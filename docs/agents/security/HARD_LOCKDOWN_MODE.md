# HARD_LOCKDOWN_MODE

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/HARD_LOCKDOWN_MODE/main.py` (67 lines)

## Purpose

_No module docstring yet._

## Class `HardLockdownMode`

Velaris Hard Lockdown Mode
- Full operational freeze for all agents except core security processes
- Every action is denied except explicit whitelist
- Overrides Soft Lockdown

- `__init__()`
- `enabled()`
- `enable()`
- `disable()`
- `is_enabled()`
- `attempt(action)` — Returns True only if:
- `get_logs()`

## Depends on

- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan104_unauthenticated_writes.py`
