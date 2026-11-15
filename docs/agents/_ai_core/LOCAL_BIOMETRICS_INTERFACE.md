# LOCAL_BIOMETRICS_INTERFACE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/LOCAL_BIOMETRICS_INTERFACE/main.py` (80 lines)

## Purpose

_No module docstring yet._

## Class `LocalBiometricsInterface`

Velaris Local Biometrics Interface
- Offline biometric template storage: salted scrypt hashes in VELARIS_DATA (owner-only, shared by workers)
- EXACT string match only: a real sensor never produces identical captures twice, so this agent compares
  enrolled strings (a stand-in for a real matcher), it does not score similarity
- Enrolling or changing a template needs the person themselves or a security admin, and a change needs proof
  of the current template; 5 failed verifications in a row lock that user for 15 minutes

- `__init__()`
- `enroll(user, biometrics)` — biometrics = {"finger": "...", "face": "...", "voice": "..."} (any non-empty subset).
- `verify(user, biometrics)`
- `update(user, current, biometrics)` — Replace or add templates. `current` must verify first (a stolen session cannot swap the enrolment).
- `list_users()`

## Depends on

- `velaris.agentkit.secure`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/LOCAL_BIOMETRICS_INTERFACE/templates.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan89_aicore.py`
