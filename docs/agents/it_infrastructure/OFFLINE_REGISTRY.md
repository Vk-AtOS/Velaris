# OFFLINE_REGISTRY

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/OFFLINE_REGISTRY/main.py` (27 lines)

## Purpose

_No module docstring yet._

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
