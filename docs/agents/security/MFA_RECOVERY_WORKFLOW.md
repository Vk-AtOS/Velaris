# MFA_RECOVERY_WORKFLOW

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/MFA_RECOVERY_WORKFLOW/main.py` (110 lines)

## Purpose

_No module docstring yet._

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
