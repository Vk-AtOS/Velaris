# PIN_UNLOCK_LAYER

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/PIN_UNLOCK_LAYER/main.py` (79 lines)

## Purpose

PIN unlock layer: per-user PINs with a locked/unlocked flag and a lockout after repeated wrong PINs.

register_pin(user, pin) stores a salted scrypt hash of a PIN of 4-12 ASCII digits and marks the user locked; False for a
bad PIN, for a user who already has one (a PIN cannot be changed here) and for a caller who is neither that user nor a
security admin (the caller's id must equal `user`; without this anyone could claim a name that has no PIN yet). unlock(user, pin) marks the user unlocked and
returns True for the right PIN; 5 wrong PINs in a row lock the user out for 15 minutes, the right PIN included. Unknown
users always fail, cost the same hashing work and leave no state behind. lock(user) relocks a registered user (same caller rule, so nobody can lock others out);
is_locked(user) is True for a locked user and for an unknown one.
State: <VELARIS_DATA>/agents/PIN_UNLOCK_LAYER/pins.json (hashes and flags) and throttle.json, owner-only and shared by
every worker.
Refusals are False returns; nothing is raised.

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
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/PIN_UNLOCK_LAYER/pins.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_kan88_auth_agents.py`
