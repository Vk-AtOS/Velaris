# MFA_RECOVERY_WORKFLOW

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/MFA_RECOVERY_WORKFLOW/main.py` (123 lines)

## Purpose

MFA recovery workflow: one-time recovery codes that yield a one-time reset token, used to record a new credential hash.

issue_recovery_code(user) returns a fresh random 8-digit code, replacing any earlier code and pending token: security
admins only, None when refused. verify_recovery_code(user, code) may be called only by that user or a security admin; a
correct, unexpired (15 minutes), unused code is consumed and the reset token is returned to that caller, otherwise None.
5 wrong codes in a row lock the user for 15 minutes, the right code included. verify_reset_token(user, token) says
whether a token is live (10 minutes, single use). reset_credentials(user, token, new_hash) consumes the token and stores
new_hash (a hash made by the caller, 1-512 characters, never a password), for the user or a security admin; False
otherwise. credential_hash(user) returns the stored hash or None. Codes are kept as salted scrypt hashes and tokens as
SHA-256 digests; every check_caller decision is traced. Delivering the code to the user is not done here.
State: <VELARIS_DATA>/agents/MFA_RECOVERY_WORKFLOW/recovery.json and throttle.json, owner-only, shared by workers and
kept across restarts. Refusals return None or False; nothing is raised.

## Class `MFARecoveryWorkflow`

Velaris MFA Recovery Workflow
- A security admin issues a one-time recovery code (random, hashed, expires, 5 wrong tries lock the user)
- A correct code is consumed and returns one reset token to the verifier (the user or a security admin)
- The token is single use and is consumed by reset_credentials, which records the new credential hash
State lives in VELARIS_DATA, so it is shared by workers and survives a restart.

- `__init__()`
- `issue_recovery_code(user)` — A fresh 8-digit code (replacing any earlier one), or None when the caller may not issue one.
- `verify_recovery_code(user, code)` — The reset token (once) for a correct, unexpired, unused code; None otherwise.
- `verify_reset_token(user, token)`
- `reset_credentials(user, token, new_hash)` — Consume the token and record `new_hash` (a hash made by the caller, never a password) as the user's credential.
- `credential_hash(user)`

## Depends on

- `velaris.agentkit.secure`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/MFA_RECOVERY_WORKFLOW/recovery.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan88_auth_agents.py`
