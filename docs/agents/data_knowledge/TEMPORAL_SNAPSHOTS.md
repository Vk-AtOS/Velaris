# TEMPORAL_SNAPSHOTS

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/TEMPORAL_SNAPSHOTS/main.py` (76 lines)

## Purpose

Temporal snapshots: stores labelled, timestamped copies of any JSON-serialisable data and retrieves or compares them.

TemporalSnapshots(): create_snapshot(label, data) appends {label, timestamp, data} and
returns it (labels are not required to be unique); list_snapshots() returns labels;
restore(label) returns the data of the first snapshot with that label; compare(a, b)
returns {"a", "b", "equal"} using the last snapshot matching each label.
State: snapshots.json under velaris.intel.paths.agent_dir("TEMPORAL_SNAPSHOTS") (honours
VELARIS_DATA), rewritten in full on every create; created as [] if missing.
Failure: an unreadable or corrupt file is logged and treated as empty; restore returns
None for an unknown label and compare gives None for it; non-serialisable data raises
TypeError on save.

## Class `TemporalSnapshots`

Velaris Temporal Snapshots
- Stores timestamped snapshots of any data structure (owner-only file, atomic and locked across workers)
- Allows restoring, listing, and comparing snapshots
- A label used twice keeps both snapshots; restore and compare always use the NEWEST one

- `__init__()`
- `snaps()`
- `create_snapshot(label, data)`
- `list_snapshots()`
- `restore(label)`
- `compare(a, b)`

## Depends on

- `velaris.agentkit.state`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan93_agents.py`
