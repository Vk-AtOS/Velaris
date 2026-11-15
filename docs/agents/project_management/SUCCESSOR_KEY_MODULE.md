# SUCCESSOR_KEY_MODULE

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/SUCCESSOR_KEY_MODULE/main.py` (52 lines)

## Purpose

Successor key module: holds the SHA-256 hash of one successor key for emergency transfer and verifies a presented key against it.

SuccessorKeyModule: set_successor_key(key) stores the hash only if none is set (else
False); wipe_key() clears it; verify(key) compares hashes; has_key(). The owner check is
not done here (the caller must do it), and wipe_key has no authorisation of its own. The
hash is unsalted and compared with ==, not a constant-time comparison.
State: in memory only (self.successor_hash), lost on restart.
Failure: verify returns False when no key is set or on mismatch; a non-string key raises
AttributeError.

## Class `SuccessorKeyModule`

Velaris Successor Key Module
- Stores and verifies a single successor key for catastrophic transfer
- Only owner (verified elsewhere) can set it
- Verifies successor token for emergency unlock

- `__init__()`
- `set_successor_key(key)` — Set once. Cannot be overwritten unless wiped.
- `wipe_key()`
- `verify(key)`
- `has_key()`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`
