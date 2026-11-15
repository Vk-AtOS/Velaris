# OWNER_VERIFICATION

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/OWNER_VERIFICATION/main.py` (64 lines)

## Purpose

_No module docstring yet._

## Class `OwnerVerification`

Velaris Owner Verification Module
- Uses fingerprint, face, and voice templates for strong local verification
- All offline; each template is stored as a salted scrypt hash (an EXACT match is required: this
  agent compares enrolled strings, it does not do fuzzy biometric matching)
- Enrolling or replacing the owner needs a security admin and is traced
- 5 failed verifications in a row lock verification for 15 minutes

- `__init__()`
- `owner_templates()`
- `enroll(fingerprint, face, voice)` — Registers the *single real owner*. Only a security admin may do it, first time or replacement.
- `verify(fingerprint, face, voice)`
- `partial_verify(**kwargs)` — Two or more factors, ALL of which must match (one matching factor is never enough).

## Depends on

- `velaris.agentkit.secure`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/OWNER_VERIFICATION/owner.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_kan88_auth_agents.py`
