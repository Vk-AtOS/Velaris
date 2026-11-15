# MEMORY_DRIFT_DETECTOR

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/MEMORY_DRIFT_DETECTOR/main.py` (85 lines)

## Purpose

Memory drift detector: measures how far new data has moved from a stored baseline, per label.
MemoryDriftDetector.set_baseline(label, data) stores a dict and saves it. get_baseline(label) returns
it or None. drift_score(label, new_data) is the percentage (0-100) of keys, over the union of old and
new keys, whose values differ; with no baseline it returns 100.0, and 0.0 when both are empty.
detect(label, new_data) returns {"label", "score", "status"} with status STABLE below 20, DRIFT below
60, otherwise SEVERE. Plain key-by-key equality, not a statistical test.
State: <VELARIS_DATA>/agents/MEMORY_DRIFT_DETECTOR/baseline.json (created as {} if absent).
Failure: an unreadable baseline file is logged as a warning and treated as empty; a failed write
raises OSError; non-dict data raises AttributeError.

## Class `MemoryDriftDetector`

Velaris Memory Drift Detector
- Tracks reference states for components
- Detects drift between the stored baseline and new data
- Computes drift magnitude (0–100 scale)

- `__init__()`
- `set_baseline(label, data)`
- `get_baseline(label)`
- `drift_score(label, new_data)`
- `detect(label, new_data)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`
