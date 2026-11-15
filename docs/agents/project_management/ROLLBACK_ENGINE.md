# ROLLBACK_ENGINE

- **Department:** `project_management`
- **Status (static inventory):** `real`
- **Source:** `departments/project_management/ROLLBACK_ENGINE/main.py` (70 lines)

## Purpose

Rollback engine: saves named state snapshots to disk and returns them on rollback.

create_snapshot(name, state) writes <name>.json and logs CREATE (overwrites an existing
snapshot); load_snapshot(name) reads it; rollback(name) returns the snapshot state and logs
ROLLBACK, it does not apply the state anywhere; get_log() returns the history list. Names must
be 1-100 letters, digits, "_", "-" or "." starting with a letter or digit, else ValueError;
a missing snapshot raises FileNotFoundError. State: snapshots/ and rollback.log (a JSON list)
under <VELARIS_DATA>/agents/ROLLBACK_ENGINE; an unreadable log is reset with a warning.

## Class `RollbackEngine`

Velaris Rollback Engine
- Stores snapshots of system state (owner-only files, written atomically)
- Allows reverting to any previous snapshot
- Maintains a rollback history log (bounded, locked, shared by every worker)

- `__init__()`
- `create_snapshot(name, state)`
- `load_snapshot(name)`
- `rollback(name)`
- `get_log()`

## Depends on

- `velaris.agentkit.secure`
- `velaris.agentkit.state`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_kan94_pm_agents.py`
