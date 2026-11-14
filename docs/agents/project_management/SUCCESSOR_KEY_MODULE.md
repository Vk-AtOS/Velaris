# SUCCESSOR_KEY_MODULE

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/SUCCESSOR_KEY_MODULE/main.py` (41 lines)

## Purpose

_No module docstring yet._

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
- **tests:** none found
