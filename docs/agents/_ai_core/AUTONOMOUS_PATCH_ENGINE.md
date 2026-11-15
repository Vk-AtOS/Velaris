# AUTONOMOUS_PATCH_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/AUTONOMOUS_PATCH_ENGINE/main.py` (85 lines)

## Purpose

Autonomous patch engine: overlays a JSON patch (a dict of field changes) on a dict and keeps an audit history.

validate_patch(patch) is True only when the patch has a text "target" and a dict "changes" (at most 200 keys, all text,
JSON values). simulate_patch(original, patch) returns a copy of original with the changes overlaid; an invalid patch
raises ValueError. apply_patch(original, patch) needs an authenticated caller (PermissionError otherwise), validates,
and returns the updated COPY; it records {"patch", "status": "COMPUTED", "by", "ts", "before", "after"} (sha256 of the
original and of the result). The status is COMPUTED, not APPLIED, because this engine never edits any module, file or
store named by "target": whoever calls it decides what to do with the returned copy. get_history() returns a copy.
State: <VELARIS_DATA>/agents/AUTONOMOUS_PATCH_ENGINE/patch_history.json (JsonState: owner-only, atomic, shared by all
workers, the newest 1,000 entries). Write errors (OSError) propagate.

## Class `AutonomousPatchEngine`

Velaris Autonomous Patch Engine
- Computes the result of offline JSON patches and records who asked for what
- Stores patch history
- Validates and simulates patches before computing

- `__init__()`
- `history()`
- `validate_patch(patch)`
- `simulate_patch(original, patch)`
- `apply_patch(original, patch)`
- `get_history()`

## Depends on

- `velaris.agentkit.state`
- `velaris.core.access`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_r3_patch_evolution_search_clbpp.py`
