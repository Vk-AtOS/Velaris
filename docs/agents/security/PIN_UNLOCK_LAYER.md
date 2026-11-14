# PIN_UNLOCK_LAYER

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/PIN_UNLOCK_LAYER/main.py` (44 lines)

## Purpose

_No module docstring yet._

## Class `PINUnlockLayer`

Velaris PIN Unlock Layer
- Stores per-user PIN hashes
- Validates PIN input
- Handles lock / unlock states

- `__init__()`
- `register_pin(user, pin)`
- `unlock(user, pin)`
- `lock(user)`
- `is_locked(user)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
