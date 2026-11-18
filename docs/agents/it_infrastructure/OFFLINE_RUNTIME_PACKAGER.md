# OFFLINE_RUNTIME_PACKAGER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/OFFLINE_RUNTIME_PACKAGER/main.py` (87 lines)

## Purpose

Offline runtime packager: bundles a Velaris source folder into a tar archive for offline installs, leaving secrets out.

package(source_dir, out_name="velaris_offline.tar") requires source_dir to hold "agents" and "tests" (ValueError
otherwise), writes an uncompressed tar under the top-level name "velaris" and returns its path. Files and folders
matching EXCLUDE_NAMES (.env files, keys and certificates, databases, .jsonl logs, credentials*, secrets*, .git,
virtualenvs, caches, exports) and anything that is not a plain file or folder (symlinks, devices) are never packed, and
owner ids are zeroed. out_name must be a plain file name ending in .tar (no separators, no ".."), else ValueError.
inspect_package(tar_path) returns {"count", "files": the first ten names} for a package inside this agent's exports
folder only (ValueError for any other path, FileNotFoundError if it is absent).
State: <VELARIS_DATA>/agents/OFFLINE_RUNTIME_PACKAGER/exports/, archives owner-only (0600). Exclusion is by file name, not
by content, and no caller check is made here.

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
