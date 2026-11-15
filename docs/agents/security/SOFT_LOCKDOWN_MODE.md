# SOFT_LOCKDOWN_MODE

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/SOFT_LOCKDOWN_MODE/main.py` (67 lines)

## Purpose

_No module docstring yet._

## Class `SoftLockdownMode`

Velaris Soft Lockdown Mode
- Restricts high-risk actions, but allows normal operations
- Tracks lockdown Enable/Disable state
- Logs attempted restricted actions

- `__init__()`
- `enabled()`
- `enable()`
- `disable()`
- `is_enabled()`
- `attempt(action)` — Returns True if action is allowed.
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
