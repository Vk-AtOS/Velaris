# SKILLPACK_LOADER

- **Department:** `operations`
- **Status (static inventory):** `real`
- **Source:** `departments/operations/SKILLPACK_LOADER/main.py` (55 lines)

## Purpose

_No module docstring yet._

## Class `SkillpackLoader`

Velaris Skillpack Loader
- Loads modular skillpacks (JSON-based)
- Registers skill functions
- Enables dynamic capability injection

- `__init__()`
- `load_skillpack(name, data)`
- `unload_skillpack(name)`
- `get_skillpack(name)`
- `list_skillpacks()`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`
