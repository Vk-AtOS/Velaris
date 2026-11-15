# DIGITAL_TWIN_XR_ENGINE

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/DIGITAL_TWIN_XR_ENGINE/main.py` (66 lines)

## Purpose

Digital twin XR engine: in-memory store of named twin dicts with diff and merge (no XR or simulation).

create_twin(name, data) (False if it exists), update_twin(name, data) (shallow merge; False if
unknown), get_twin(name) ({} if unknown), diff(a, b) returns the fields that differ as
{field: {"a": ..., "b": ...}}, merge(target, source) copies source fields into target (False if
either is unknown). Names are lower-cased. create_twin keeps the caller's dict, not a copy.
State: a dict in memory only, lost on restart.

## Class `DigitalTwinXREngine`

Velaris Digital Twin / XR Engine (Offline Simulation)
- Maintains abstract digital-twin state models
- Allows updating and querying XR-friendly state data
- Provides diff and merge operations

- `__init__()`
- `create_twin(name, data)`
- `update_twin(name, data)`
- `get_twin(name)`
- `diff(a, b)` — Compares two digital twins and returns differing fields.
- `merge(target, source)` — Merge source twin fields into target twin.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`
