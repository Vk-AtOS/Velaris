# OFFLINE_REGISTRY

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/OFFLINE_REGISTRY/main.py` (44 lines)

## Purpose

Offline registry: a small persistent key-value store kept in one JSON file.

OFFLINE_REGISTRYAgent(path=""): health_check(); set(key, value) stores the value and
rewrites the whole file via velaris.intel.paths.write_private (owner-only); get(key,
default=None) reads from the in-memory copy loaded at construction.
State: registry.json under the agent data dir (velaris.intel.paths.agent_file, honours
VELARIS_DATA), or the given path. Each instance holds its own copy, so concurrent
instances can overwrite each other.
Failure: an unreadable or corrupt file is logged and the registry starts empty; set()
with a non-JSON-serialisable value raises TypeError.

## Class `OFFLINE_REGISTRYAgent`

- `__init__(path)`
- `health_check()`
- `set(k, v)`
- `get(k, default)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_memory_substrate.py`, `velaris/tests/test_no_state_in_source_tree.py`
