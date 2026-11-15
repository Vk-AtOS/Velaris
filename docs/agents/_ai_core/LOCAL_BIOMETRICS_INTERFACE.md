# LOCAL_BIOMETRICS_INTERFACE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/LOCAL_BIOMETRICS_INTERFACE/main.py` (70 lines)

## Purpose

Local biometrics interface: stores SHA-256 hashes of biometric strings per user and checks presented ones against them.

LocalBiometricsInterface: enroll(user, biometrics) stores a hash per factor
({"finger"|"face"|"voice": text}, any key accepted) and returns False if the user is
already enrolled; verify(user, biometrics) is True only if the user exists, at least one
factor is presented, and every presented factor equals its enrolled hash; update(user,
biometrics) overwrites or adds factor hashes for an enrolled user; list_users() returns
the enrolled user names.
This is an exact-hash comparison, not fuzzy biometric matching, and the hash is unsalted.
State: in memory only (self.templates), lost on restart.
Failure: unknown user, empty input or any unmatched or un-enrolled factor returns False
(fail closed); non-string factor values raise AttributeError.

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
- **tests:** `velaris/tests/test_agents_coverage_c.py`
