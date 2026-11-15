# PIN_UNLOCK_LAYER

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/PIN_UNLOCK_LAYER/main.py` (55 lines)

## Purpose

PIN unlock layer: per-user SHA-256 PIN hashes with a locked or unlocked flag.

PINUnlockLayer: register_pin(user, pin) stores the hash and starts locked (False if
already registered); unlock(user, pin) clears the lock on a matching PIN; lock(user)
re-locks a registered user; is_locked(user). There is no attempt counter or lockout, and
the hash is unsalted.
State: in memory only (self.pins, self.locked), lost on restart.
Failure: an unknown user or wrong PIN makes unlock return False; is_locked is True for an
unknown user (fail closed); a non-string PIN raises AttributeError.

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
- **tests:** `velaris/tests/test_agents_coverage_b.py`
