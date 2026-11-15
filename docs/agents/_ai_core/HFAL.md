# HFAL

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/HFAL/main.py` (89 lines)

## Purpose

HFAL (Human-Friendly Auth Layer): issues PIN-backed session tokens that expire, and validates them.

create_session(user, pin) returns a random URL-safe token (not derived from the user or the pin) and stores the user, a
salted scrypt hash of the pin and an expiry 8 hours ahead; expired sessions are dropped on each create. An empty or
non-text user or pin raises ValueError, as do more than 5000 open sessions. validate(token, pin) is True only for a live
token with the matching pin; 5 wrong pins in a row lock that token for 15 minutes (the right pin is refused too), and an
unknown or expired token costs the same hashing work and returns False. destroy_session(token) deletes it and returns
True, or False if unknown.
State: <VELARIS_DATA>/agents/HFAL/sessions.db (JSON, owner-only, atomic, locked across workers) and throttle.json for the
lockout counters. A sessions file that cannot be parsed is set aside as sessions.db.corrupt-<time> and the agent starts
with no sessions, so every validate() fails closed.

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
