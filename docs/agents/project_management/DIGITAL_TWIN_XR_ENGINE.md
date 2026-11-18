# DIGITAL_TWIN_XR_ENGINE

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/DIGITAL_TWIN_XR_ENGINE/main.py` (68 lines)

## Purpose

Digital twin / XR engine: named in-memory state dicts with update, diff and merge (no XR rendering, no device link).

create_twin(name, data) (False if the name exists), update_twin(name, data) (merges top-level keys; False if unknown),
get_twin(name) (a copy; {} if unknown), diff(a, b) returns {field: {"a": value, "b": value}} for every field that
differs, treating an unknown twin as empty, and merge(target, source) copies the source's fields over the target's
(False if either is unknown). Names are case-insensitive. Data is deep-copied in and out, so callers cannot edit a twin
in place.
State: a dict in memory only, lost on restart. Failure: a non-string name raises AttributeError; no caller check is made.

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
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan94_pm_agents.py`
