# DEEP_AUDIT_ENGINE

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/DEEP_AUDIT_ENGINE/main.py` (116 lines)

## Purpose

Deep audit engine: pins a checksum baseline per name, detects drift from it, and keeps a hash-chained audit log.

checksum(data) is the SHA-256 of the sorted-key JSON form. audit(name, data) records the checksum and who audited: the
first audit of a name pins its baseline (any caller, or none), and auditing the name again moves the baseline and so
needs a security admin (check_caller; the refusal dict is returned otherwise). It returns the log entry {name, checksum,
by, prev, hash}, or {"status": "invalid", ...} for an empty name or more than 5000 names. detect_drift(name, new_data)
is True when the checksum differs from the baseline, and also for a name never audited. verify_log() re-walks the chain
and checks that each baseline equals its newest log entry; False means the file was altered.
State: <VELARIS_DATA>/agents/DEEP_AUDIT_ENGINE/audit_log.json (owner-only, atomic, locked) and audit.key. The log keeps
the newest 2000 entries; the dropped prefix is replaced by a checkpoint signed with the key (HMAC-SHA256). The key sits
beside the log, so verify_log() catches damage and edits made without the key, not an attacker who can read both files.
Failure: data that cannot be written as JSON raises TypeError.

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
