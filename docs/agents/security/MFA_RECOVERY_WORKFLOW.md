# MFA_RECOVERY_WORKFLOW

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/MFA_RECOVERY_WORKFLOW/main.py` (70 lines)

## Purpose

MFA recovery workflow: simulated one-time recovery codes and reset tokens (not production-grade).

MFARecoveryWorkflow: issue_recovery_code(user) returns a 6-digit code and stores its hash;
verify_recovery_code(user, code) compares hashes in constant time and consumes the code on success;
issue_reset_token(user) returns a 16-char random token;
verify_reset_token(user, token); reset_credentials(user, new_hash) only checks a reset
token exists for the user and deletes it, it does not change any credential. Codes and
tokens come from the secrets module; there is no rate limit and no expiry.
State: in memory only (self.recovery_codes, self.reset_tokens), lost on restart.
Failure: unknown users return False; a non-string code raises AttributeError.

## Class `MFARecoveryWorkflow`

Velaris MFA Recovery Workflow
- Issues one-time recovery codes
- Verifies recovery codes
- Resets authentication credentials

- `__init__()`
- `issue_recovery_code(user)`
- `verify_recovery_code(user, code)`
- `issue_reset_token(user)`
- `verify_reset_token(user, token)`
- `reset_credentials(user, new_hash)` — This simulates resetting stored auth material.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`
