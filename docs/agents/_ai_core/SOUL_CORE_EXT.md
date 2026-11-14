# SOUL_CORE_EXT

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/SOUL_CORE_EXT/main.py` (44 lines)

## Purpose

SOUL_CORE_EXT: versioned operating settings for this Velaris instance.

The name promises a "soul"; what it does is keep a small document of
settings (any JSON values) where every update is a new recorded version with
who made it and what changed. snapshot() is the current settings, history()
the changes, at(ts) the settings at an earlier time, rollback(version)
restores an earlier version (recorded as a new change). Changes and rollbacks
need a governance admin and are recorded against the current caller
(velaris.core.access), never an argument. Stored owner-only
under this agent's state directory; survives restart.

## Class `SOUL_CORE_EXTAgent`

- `__init__()`
- `health_check()`
- `update(data, by)` — Merge `data` into the settings, as the current caller. "updated" is True only when something changed.
- `snapshot()`
- `history(key)`
- `at(ts)`
- `rollback(version, by)`

## Depends on

- `velaris.agentkit.aicore_b_versioned`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_self.py`, `velaris/tests/test_layer3_selfidentity.py`
