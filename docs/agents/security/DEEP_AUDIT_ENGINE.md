# DEEP_AUDIT_ENGINE

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/DEEP_AUDIT_ENGINE/main.py` (103 lines)

## Purpose

_No module docstring yet._

## Class `DeepAuditEngine`

Velaris Deep Audit Engine
- Performs integrity scanning of data structures; computes checksums
- Detects drift against a PINNED baseline per name: the first audit of a name sets it, and only a security
  admin can move it (a re-audit), so a tampered artifact cannot be "re-audited clean" by any caller
- The log is owner-only, atomic, locked, hash-chained and records who audited; trimming old entries leaves a
  signed checkpoint of the dropped prefix, so verify_log() still holds and a hidden truncation does not

- `__init__()`
- `log()`
- `checksum(data)`
- `audit(name, data)` — Record `data` for `name`. The first audit of a name pins its baseline; moving an existing baseline needs a
- `detect_drift(name, new_data)`
- `verify_log()`

## Depends on

- `velaris.agentkit.state`
- `velaris.core.access`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan88_security_agents.py`
