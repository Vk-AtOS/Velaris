# SKILLPACK_LOADER

- **Department:** `operations`
- **Status (static inventory):** `real`
- **Source:** `departments/operations/SKILLPACK_LOADER/main.py` (75 lines)

## Purpose

Skillpack loader: stores named JSON skillpacks as files and reads them back; it executes nothing.

load_skillpack(name, data) writes <name>.json (False if it exists; the create is exclusive, so two workers cannot both
win); unload_skillpack(name) deletes it (False if absent); get_skillpack(name) returns the stored dict or None;
list_skillpacks() returns the sorted names on disk. A name must be a plain file name (no path separators, no "..", not
starting with "."), otherwise ValueError, and the resolved path must stay inside the folder. Data that cannot be written
as JSON (NaN included) raises, and a pack over the state size cap (1 MiB by default) raises ValueError.
State: <VELARIS_DATA>/agents/SKILLPACK_LOADER/skillpacks/, one owner-only file per pack, written atomically;
self.registry is only a per-instance cache of the packs this instance loaded or read. No caller check is made.

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
