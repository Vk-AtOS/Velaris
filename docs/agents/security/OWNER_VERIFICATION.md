# OWNER_VERIFICATION

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/OWNER_VERIFICATION/main.py` (75 lines)

## Purpose

Owner verification: checks the fingerprint, face and voice templates of the single owner by exact string match.

enroll(fingerprint, face, voice) stores a salted scrypt hash of each non-empty template and replaces any earlier owner:
security admins only (check_caller, traced). verify(fingerprint, face, voice) is True only when all three match.
partial_verify(**factors) takes two or more of finger, face and voice and is True only when all of them match; a single
factor, or an unknown factor name, is False. With nobody enrolled everything is False. 5 failed verifications in a row
lock verification for 15 minutes, the right templates included; a success or a new enrolment clears the count.
owner_templates returns the stored hashes. This compares enrolled strings; it does no fuzzy biometric matching.
State: <VELARIS_DATA>/agents/OWNER_VERIFICATION/owner.json (hashes only) and throttle.json, owner-only and shared by
workers. Refusals are False returns; nothing is raised.

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
