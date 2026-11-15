# SUCCESSOR_KEY_MODULE

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/SUCCESSOR_KEY_MODULE/main.py` (75 lines)

## Purpose

Successor key module: stores one successor key as a salted hash and verifies a presented key against it.

set_successor_key(key) stores the scrypt hash of a key of at least 8 characters: security admins only (check_caller,
traced), and False if a key is already set (it must be wiped first). wipe_key() removes it, security admins only.
verify(key) is True only for the stored key (constant-time compare); 5 wrong keys in a row lock verification for 15
minutes, during which the right key is refused too, and with no key set it is always False. has_key() says whether one
is set. Verifying grants nothing by itself: whatever transfer the key gates is the caller's to perform.
State: <VELARIS_DATA>/agents/SUCCESSOR_KEY_MODULE/successor.json (the hash only) and throttle.json, owner-only and shared
by every worker. Refusals are False returns; nothing is raised.

## Class `SuccessorKeyModule`

Velaris Successor Key Module
- Stores and verifies a single successor key for catastrophic transfer (scrypt hash, persisted in VELARIS_DATA)
- Setting and wiping the key need a security admin and are traced
- Verification is constant-time and locks after 5 wrong keys in a row

- `__init__()`
- `successor_hash()`
- `set_successor_key(key)` — Set once. Cannot be overwritten unless wiped.
- `wipe_key()`
- `verify(key)`
- `has_key()`

## Depends on

- `velaris.agentkit.secure`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/SUCCESSOR_KEY_MODULE/successor.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_kan94_pm_agents.py`
