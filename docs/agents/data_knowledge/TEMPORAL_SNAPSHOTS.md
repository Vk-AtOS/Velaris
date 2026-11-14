# TEMPORAL_SNAPSHOTS

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/TEMPORAL_SNAPSHOTS/main.py` (71 lines)

## Purpose

_No module docstring yet._

## Class `TemporalSnapshots`

Velaris Temporal Snapshots
- Stores timestamped snapshots of any data structure
- Allows restoring, listing, and comparing snapshots

- `__init__()`
- `create_snapshot(label, data)`
- `list_snapshots()`
- `restore(label)`
- `compare(a, b)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`
