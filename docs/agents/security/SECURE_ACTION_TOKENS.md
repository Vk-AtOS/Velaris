# SECURE_ACTION_TOKENS

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SECURE_ACTION_TOKENS/main.py` (56 lines)

## Purpose

_No module docstring yet._

## Class `SecureActionTokens`

Velaris Secure Action Tokens
- Generates short-lived capability tokens
- Validates tokens using HMAC-SHA256
- Prevents replay via timestamp window

- `__init__(ttl_seconds)`
- `generate(action)`
- `validate(token, action)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ZERO_TRUST_PIPELINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_dept_security_stubs.py`, `velaris/tests/test_no_silent_except.py`, `velaris/tests/test_private_files.py`
