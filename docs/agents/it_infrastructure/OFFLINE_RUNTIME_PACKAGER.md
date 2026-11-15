# OFFLINE_RUNTIME_PACKAGER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/OFFLINE_RUNTIME_PACKAGER/main.py` (75 lines)

## Purpose

_No module docstring yet._

## Class `OfflineRuntimePackager`

Offline Runtime Packager
- Bundles Velaris modules into a tar archive
- Ensures offline execution compatibility
- Validates package contents before export

- `__init__()`
- `package(source_dir, out_name)`
- `inspect_package(tar_path)`

## Depends on

- `velaris.agentkit.secure`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan90_infra.py`
