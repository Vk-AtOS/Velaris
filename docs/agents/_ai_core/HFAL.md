# HFAL

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/HFAL/main.py` (81 lines)

## Purpose

_No module docstring yet._

## Class `HFAL`

HFAL — Human-Friendly Auth Layer
Velaris Authentication Module
- Simplified human-readable auth tokens
- PIN-based verification
- Session validation

- `__init__()`
- `create_session(user, pin)`
- `validate(token, pin)`
- `destroy_session(token)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_no_silent_except.py`, `velaris/tests/test_private_files.py`
