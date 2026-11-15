# MODEL_REGISTRY_CANARY

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/MODEL_REGISTRY_CANARY/main.py` (77 lines)

## Purpose

Model registry canary: tracks model versions and their canary rollout percentage.

Models are keyed "name:version" with {active, canary, checksum}. register_model(name, version,
checksum) adds an inactive entry (False if it exists); activate/deactivate(name, version) set
the flag and reset canary to 0; set_canary(name, version, percent) accepts a whole number 0..100 (a bool, float or text is refused); get_model
returns the entry or None. Every mutator returns False for an unknown model (or a refused
percent) instead of raising. Nothing here routes traffic or verifies the checksum.
State: <VELARIS_DATA>/agents/MODEL_REGISTRY_CANARY/registry.json (owner-only, atomic, locked
across workers, created on the first write); a file that cannot be parsed is set aside as
registry.json.corrupt-<time> and the registry starts empty.

## Class `ModelRegistryCanary`

Velaris Model Registry + Canary Deploy System
- Registers model versions
- Activates/deactivates models
- Canary rollout controller (percentage-based)
- Metadata + checksum tracking

- `__init__()`
- `registry()`
- `register_model(name, version, checksum)`
- `activate(name, version)`
- `deactivate(name, version)`
- `set_canary(name, version, percent)` — Whole percent 0..100. Booleans, floats and text are refused (a string used to raise TypeError).
- `get_model(name, version)`

## Depends on

- `velaris.agentkit.state`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan89_aicore.py`
