# SECURE_ACTION_TOKENS

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SECURE_ACTION_TOKENS/main.py` (72 lines)

## Purpose

_No module docstring yet._

## Class `SecureActionTokens`

Velaris Secure Action Tokens
- Generates short-lived capability tokens
- Validates tokens using HMAC-SHA256
- Single use: a token is accepted once; a replay inside its lifetime is refused

- `__init__(ttl_seconds)`
- `generate(action)`
- `validate(token, action)`

## Depends on

- `velaris.agentkit.state`
- `velaris.intel.paths`

## State and configuration

- state file: `<VELARIS_DATA>/agents/SECURE_ACTION_TOKENS/used.json`

## Called by

- **other agents:** `ZERO_TRUST_PIPELINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_dept_security_stubs.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_no_silent_except.py`, `velaris/tests/test_private_files.py`
