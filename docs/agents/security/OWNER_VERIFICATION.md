# OWNER_VERIFICATION

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/OWNER_VERIFICATION/main.py` (53 lines)

## Purpose

_No module docstring yet._

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
- **tests:** none found
