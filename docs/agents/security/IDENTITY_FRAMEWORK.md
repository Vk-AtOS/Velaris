# IDENTITY_FRAMEWORK

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/IDENTITY_FRAMEWORK/main.py` (93 lines)

## Purpose

Identity framework: stores user profiles with salted password hashes and checks passwords.

create_identity(username, password, meta) hashes the password (PBKDF2-HMAC-SHA256, 200000 rounds, random 16-byte salt) and
returns False if the username exists. validate_identity(username, password) returns True only for a matching password
(constant-time compare), False for an unknown user. update_meta(username, meta) merges into the profile (False if unknown);
get_meta(username) returns the profile dict or None. There is no caller check, lockout or password policy.
State: <VELARIS_DATA>/agents/IDENTITY_FRAMEWORK/identity.db (JSON, owner-only file). If that file cannot be parsed or is not
a JSON object, construction raises RuntimeError rather than starting empty and overwriting the accounts.

## Class `IdentityFramework`

Velaris Identity Framework
- Creates, stores, and validates identity profiles
- Password hashing
- Identity metadata registry

- `__init__()`
- `create_identity(username, password, meta)`
- `validate_identity(username, password)`
- `update_meta(username, meta)`
- `get_meta(username)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_no_silent_except.py`, `velaris/tests/test_private_files.py`
