# SECURE_ACTION_TOKENS

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SECURE_ACTION_TOKENS/main.py` (85 lines)

## Purpose

Secure action tokens: short-lived, single-use HMAC-SHA256 tokens that authorise one named action.

SecureActionTokens(ttl_seconds=60): generate(action) returns base64(action:timestamp:nonce)
+ "." + signature; validate(token, action) returns {"status": "OK"} or {"status":
"INVALID", "reason"} with reason SignatureMismatch, ActionMismatch, Expired, Replayed or
MalformedToken. Unless the class attribute single_use is False (subclasses issuing
reusable sessions), a signature is accepted once and refused on replay within its ttl.
State: signing key sat.key (created owner-only by load_or_create_key) and used-token
record JsonState("SECURE_ACTION_TOKENS", "used.json"), both under the agent data dir
(VELARIS_DATA), shared across workers.
Failure: validate never raises on bad tokens; every malformed input maps to INVALID.

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
