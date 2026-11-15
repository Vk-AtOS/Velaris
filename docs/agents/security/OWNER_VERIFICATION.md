# OWNER_VERIFICATION

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/OWNER_VERIFICATION/main.py` (61 lines)

## Purpose

Owner verification: compares fingerprint, face and voice strings with hashes enrolled for one owner.

enroll(fingerprint, face, voice) stores the SHA-256 of each string as the single owner's templates, replacing any earlier
ones, with no check on who is enrolling. verify(...) is True only when all three hash-match. partial_verify(finger=, face=,
voice=) is True when every supplied factor matches; no factors, an unknown factor name, or any mismatch gives False. With
nothing enrolled everything is False (fails closed). It compares exact strings, so it does no biometric matching, and the
hashes are unsalted. State: in memory only, so the enrolment is lost on exit.

## Class `OwnerVerification`

Velaris Owner Verification Module
- Uses fingerprint, face, and voice templates for strong local verification
- All offline, hash-based

- `__init__()`
- `enroll(fingerprint, face, voice)` — Registers the *single real owner* of Velaris.
- `verify(fingerprint, face, voice)`
- `partial_verify(**kwargs)` — Allows partial matching (e.g., only fingerprint or only face).

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`
