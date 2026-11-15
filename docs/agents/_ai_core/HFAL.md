# HFAL

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/HFAL/main.py` (77 lines)

## Purpose

_No module docstring yet._

## Class `HFAL`

HFAL — Human-Friendly Auth Layer
Velaris Authentication Module
- Random session tokens (not derived from the user or PIN) that expire
- PIN-based verification: scrypt-salted PIN hash, constant-time compare, 5 wrong PINs lock the token
- Session validation; the store is owner-only, atomic and shared by every worker

- `__init__()`
- `sessions()`
- `create_session(user, pin)`
- `validate(token, pin)`
- `destroy_session(token)`

## Depends on

- `velaris.agentkit.secure`
- `velaris.agentkit.state`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan89_aicore.py`, `velaris/tests/test_no_silent_except.py`, `velaris/tests/test_private_files.py`
