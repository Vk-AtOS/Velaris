# MODEL_REGISTRY_CANARY

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/MODEL_REGISTRY_CANARY/main.py` (85 lines)

## Purpose

_No module docstring yet._

## Class `ModelRegistryCanary`

Velaris Model Registry + Canary Deploy System
- Registers model versions
- Activates/deactivates models
- Canary rollout controller (percentage-based)
- Metadata + checksum tracking

- `__init__()`
- `register_model(name, version, checksum)`
- `activate(name, version)`
- `deactivate(name, version)`
- `set_canary(name, version, percent)`
- `get_model(name, version)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`
