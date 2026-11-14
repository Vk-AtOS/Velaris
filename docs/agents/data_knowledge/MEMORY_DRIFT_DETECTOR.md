# MEMORY_DRIFT_DETECTOR

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/MEMORY_DRIFT_DETECTOR/main.py` (75 lines)

## Purpose

_No module docstring yet._

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
