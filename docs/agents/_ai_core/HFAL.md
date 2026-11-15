# HFAL

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/HFAL/main.py` (90 lines)

## Purpose

HFAL (Human-Friendly Auth Layer): issues short PIN-backed session tokens and validates them.

create_session(user, pin) returns a 12-hex-character token (the start of an unsalted SHA-256 of user+pin) and stores the
user and the SHA-256 of the pin. validate(token, pin) is True only for a known token whose pin hash matches; an unknown
token or wrong pin returns False. destroy_session(token) deletes it and returns True, or False if unknown. There is no
expiry and no attempt limit; the same user and pin always give the same token.
State: <VELARIS_DATA>/agents/HFAL/sessions.db (JSON, owner-only file). If it is unreadable or not a JSON object, it is
renamed to sessions.db.corrupt and the agent starts with no sessions, so every validate() fails closed.

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
