# PIN_UNLOCK_LAYER

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/PIN_UNLOCK_LAYER/main.py` (60 lines)

## Purpose

_No module docstring yet._

## Class `PINUnlockLayer`

Velaris PIN Unlock Layer
- Stores per-user PIN hashes (scrypt, random salt) in VELARIS_DATA, shared by every worker
- Validates PIN input; 5 wrong PINs in a row lock the user for 15 minutes (even for the right PIN)
- Handles lock / unlock states

- `__init__()`
- `register_pin(user, pin)`
- `unlock(user, pin)`
- `lock(user)`
- `is_locked(user)`

## Depends on

- `velaris.agentkit.secure`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/PIN_UNLOCK_LAYER/pins.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_kan88_auth_agents.py`
