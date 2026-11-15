# DEEP_AUDIT_ENGINE

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/DEEP_AUDIT_ENGINE/main.py` (73 lines)

## Purpose

Deep audit engine: records SHA-256 checksums of data and detects changes against them.

checksum(data) hashes the JSON form (sorted keys; non-JSON data raises TypeError). audit(name,
data) appends {name, checksum} to the log and saves it. detect_drift(name, new_data) compares
with the first logged entry for that name and returns True when it differs or when the name was
never audited. The log is append-only but not tamper-proof. State: audit_log.json (a JSON list)
under <VELARIS_DATA>/agents/DEEP_AUDIT_ENGINE; an unreadable file is logged and treated as empty.

## Class `DeepAuditEngine`

Velaris Deep Audit Engine
- Performs integrity scanning of data structures
- Computes checksums
- Detects drift or unauthorized changes

- `__init__()`
- `checksum(data)`
- `audit(name, data)`
- `detect_drift(name, new_data)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`
