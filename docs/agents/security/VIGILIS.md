# VIGILIS

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/VIGILIS/main.py` (156 lines)

## Purpose

VIGILIS: signatures, a deny-by-default policy check, and a file-integrity watch.

Signing      generate_test_keypair() makes an in-memory RSA-2048 key; sign_message()
             and verify_signature() use RSA-PSS with SHA-256. Verification fails
             closed: any error, a missing key or a non-bytes argument is "not valid".
             The key lives only in this object - it is for signing within one
             process (and tests), not a key-management service.

Policy       evaluate_policy(context) applies config["policies"], a list of
             {"id": ..., "effect": "allow"|"deny", "when": {conditions}}
             (conditions as in velaris.agentkit.conditions). A matching deny
             wins; otherwise a matching allow is needed. No policies, a malformed
             policy list, or context["untrusted_source"] being set: denied.
             (POLICY_CONTROLLER is the stored, versioned policy set; this is a
             check against the configuration this agent was started with.)

Integrity    baseline(paths) records the SHA-256 of files (by default every
             agent's main.py); check() reports each file that has since changed
             or disappeared. The baseline is an owner-only file, not a signed
             one: it detects accidental or unprivileged change, not an attacker
             who can also rewrite the baseline.

## Class `VigilisAgent`

- `__init__(config)`
- `health_check()`
- `generate_test_keypair()`
- `sign_message(message)` — RSA-PSS signature of `message`, or b"" (which never verifies) if there is no key or message is not bytes.
- `verify_signature(message, signature)`
- `evaluate_policy(context)`
- `baseline(paths)` — Record the current SHA-256 of each file (default: every agent's main.py).
- `check()` — Compare the watched files with the baseline. Each difference is a "high" finding.

## Depends on

- `velaris`
- `velaris.agentkit`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`
- `velaris.core.utils`

## State and configuration

- state file: `<VELARIS_DATA>/agents/VIGILIS/baseline.json`

## Called by

- **other agents:** `ENGINE`, `PRIME`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_eof.py`, `velaris/tests/test_aicore_b_prime_vcas.py`, `velaris/tests/test_dept_security_stubs.py`, `velaris/tests/test_engine.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_loader_and_fail_closed.py`, `velaris/tests/test_registry.py`, `velaris/tests/test_security_review_fixes.py`, `velaris/tests/test_system_integration.py`, `velaris/tests/test_vigilis.py`
