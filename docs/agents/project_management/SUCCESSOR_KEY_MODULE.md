# SUCCESSOR_KEY_MODULE

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/SUCCESSOR_KEY_MODULE/main.py` (65 lines)

## Purpose

_No module docstring yet._

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
