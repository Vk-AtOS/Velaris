# AUTONOMOUS_PATCH_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/AUTONOMOUS_PATCH_ENGINE/main.py` (76 lines)

## Purpose

Autonomous patch engine: applies a JSON patch (a dict of field changes) to a dict and records it in a history.

validate_patch(patch) is True only when the patch has "target" and a dict "changes". simulate_patch(original, patch)
returns a copy of original with the changes overlaid (no validation, so a patch without "changes" raises KeyError).
apply_patch(original, patch) validates, then returns the updated copy and appends {"patch", "status": "APPLIED"} to the
history; an invalid patch raises ValueError. It never edits any module or file named by "target". get_history() returns a copy.
State: <VELARIS_DATA>/agents/AUTONOMOUS_PATCH_ENGINE/patch_history.json (created as [] on start; an unreadable file is
logged and the history starts empty, and the next apply overwrites it). Write errors (OSError) propagate.

## Class `AutonomousPatchEngine`

Velaris Autonomous Patch Engine
- Applies offline-safe JSON-based patches to internal modules
- Stores patch history
- Validates and simulates patches before applying

- `__init__()`
- `validate_patch(patch)`
- `simulate_patch(original, patch)`
- `apply_patch(original, patch)`
- `get_history()`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`
