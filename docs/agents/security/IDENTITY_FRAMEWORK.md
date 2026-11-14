# IDENTITY_FRAMEWORK

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/IDENTITY_FRAMEWORK/main.py` (84 lines)

## Purpose

_No module docstring yet._

## Class `IdentityFramework`

Velaris Identity Framework
- Creates, stores, and validates identity profiles
- Password hashing
- Identity metadata registry

- `__init__()`
- `create_identity(username, password, meta)`
- `validate_identity(username, password)`
- `update_meta(username, meta)`
- `get_meta(username)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_no_silent_except.py`, `velaris/tests/test_private_files.py`
