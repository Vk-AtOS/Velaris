# MODEL_REGISTRY_CANARY

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/MODEL_REGISTRY_CANARY/main.py` (95 lines)

## Purpose

Model registry canary: tracks model versions and their canary rollout percentage.

Models are keyed "name:version" with {active, canary, checksum}. register_model(name, version,
checksum) adds an inactive entry (False if it exists); activate/deactivate(name, version) set
the flag and reset canary to 0; set_canary(name, version, percent) accepts 0..100; get_model
returns the entry or None. Every mutator returns False for an unknown model (or a percent out
of range) instead of raising. Nothing here routes traffic or verifies the checksum.
State: <VELARIS_DATA>/agents/MODEL_REGISTRY_CANARY/registry.json (created on first use); an
unreadable file is logged as a warning and treated as empty.

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
