# SKILLPACK_LOADER

- **Department:** `operations`
- **Status (static inventory):** `real`
- **Source:** `departments/operations/SKILLPACK_LOADER/main.py` (65 lines)

## Purpose

_No module docstring yet._

## Class `SkillpackLoader`

Velaris Skillpack Loader
- Loads modular skillpacks (JSON-based; one owner-only file per pack, written atomically)
- Registers skill functions
- Enables dynamic capability injection
- A pack name is a plain file name (no separators, no '..'); the resolved path must stay inside the folder,
  so neither a name nor a symlink can make a write or a delete reach another file

- `__init__()`
- `load_skillpack(name, data)`
- `unload_skillpack(name)`
- `get_skillpack(name)`
- `list_skillpacks()`

## Depends on

- `velaris.agentkit.secure`
- `velaris.agentkit.state`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan86_operations.py`
