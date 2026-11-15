# OFFLINE_RUNTIME_PACKAGER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/OFFLINE_RUNTIME_PACKAGER/main.py` (62 lines)

## Purpose

Offline runtime packager: bundles a Velaris source tree into a tar archive and lists its contents.

package(source_dir, out_name="velaris_offline.tar") writes the whole directory under the name
"velaris" into the exports folder and returns the archive path; it raises ValueError unless
source_dir exists and has "agents" and "tests" entries. out_name is joined to the exports
directory without sanitising. inspect_package(tar_path) returns {count, files (first 10)} and
raises FileNotFoundError for a missing file. No offline-compatibility check is done.
State: archives under <VELARIS_DATA>/agents/OFFLINE_RUNTIME_PACKAGER/exports; no other state.

## Class `OfflineRuntimePackager`

Offline Runtime Packager
- Bundles Velaris modules into a tar archive
- Ensures offline execution compatibility
- Validates package contents before export

- `__init__()`
- `package(source_dir, out_name)`
- `inspect_package(tar_path)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`
