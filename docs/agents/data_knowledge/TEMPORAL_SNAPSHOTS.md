# TEMPORAL_SNAPSHOTS

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/TEMPORAL_SNAPSHOTS/main.py` (78 lines)

## Purpose

Temporal snapshots: stores labelled, timestamped copies of any JSON-serialisable data and retrieves or compares them.

TemporalSnapshots(): create_snapshot(label, data) appends {label, timestamp, data} and
returns it (labels are not required to be unique); list_snapshots() returns labels;
restore(label) returns the data of the newest snapshot with that label; compare(a, b)
returns {"a", "b", "found": {"a", "b"}, "equal"} using the newest snapshot of each label;
"equal" is None when either label is unknown (nothing was compared).
State: snapshots.json under velaris.intel.paths.agent_dir("TEMPORAL_SNAPSHOTS") (honours
VELARIS_DATA), owner-only, written atomically and locked across workers; only the newest 500
snapshots are kept.
Failure: a file that cannot be parsed is set aside as snapshots.json.corrupt-<time> and the
store starts empty; restore returns None for an unknown label; non-serialisable data raises
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
