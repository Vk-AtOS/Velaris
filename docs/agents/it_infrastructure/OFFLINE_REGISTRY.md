# OFFLINE_REGISTRY

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/OFFLINE_REGISTRY/main.py` (35 lines)

## Purpose

Offline registry: a small key/value store in one local JSON file, usable without any network.

OFFLINE_REGISTRYAgent(path=""): set(k, v) stores a value under a non-empty text key (ValueError otherwise); get(k,
default=None) returns it or the default; health_check() returns {"agent", "status": "ok", "version"}.
State: <VELARIS_DATA>/agents/OFFLINE_REGISTRY/registry.json, or the path given; owner-only, written atomically and locked
across workers, so values survive a restart. A file that cannot be parsed is set aside as <name>.corrupt-<time> and the
registry starts empty; a value that cannot be written as JSON raises on set. No caller check is made.

## Class `OFFLINE_REGISTRYAgent`

A small key/value registry that works offline: one owner-only file, atomic and locked across workers.

- `__init__(path)`
- `health_check()`
- `set(k, v)`
- `get(k, default)`

## Depends on

- `velaris.agentkit.state`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan90_infra.py`, `velaris/tests/test_memory_substrate.py`, `velaris/tests/test_no_state_in_source_tree.py`
