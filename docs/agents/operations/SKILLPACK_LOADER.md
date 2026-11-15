# SKILLPACK_LOADER

- **Department:** `operations`
- **Status (static inventory):** `real`
- **Source:** `departments/operations/SKILLPACK_LOADER/main.py` (64 lines)

## Purpose

Skillpack loader: stores JSON skillpacks as files and keeps the loaded ones in a registry.

load_skillpack(name, data) writes <name>.json and registers it, returning False if the file already exists.
unload_skillpack(name) deletes the file and returns False if there is none. get_skillpack(name) returns the registered
pack, else reads the file (and registers it), else None; a file that is not valid JSON raises ValueError.
list_skillpacks() lists only packs registered in this process. The name is used in the file path without validation, and
no skill function is executed or registered here: packs are data only.
State: <VELARIS_DATA>/agents/SKILLPACK_LOADER/skillpacks/<name>.json plus an in-memory registry.

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
