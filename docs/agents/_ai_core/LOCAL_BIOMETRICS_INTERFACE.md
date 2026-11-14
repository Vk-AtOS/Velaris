# LOCAL_BIOMETRICS_INTERFACE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/LOCAL_BIOMETRICS_INTERFACE/main.py` (56 lines)

## Purpose

_No module docstring yet._

## Class `LocalBiometricsInterface`

Velaris Local Biometrics Interface
- Offline biometric template storage
- Local hashing + match scoring
- Supports finger, face, voice templates (string hashes)

- `__init__()`
- `enroll(user, biometrics)` — biometrics = {
- `verify(user, biometrics)`
- `update(user, biometrics)`
- `list_users()`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
