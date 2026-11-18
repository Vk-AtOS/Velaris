# ARGUS

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/ARGUS/main.py` (57 lines)

## Purpose

Argus: tracks source heartbeats and version signatures to flag silent or changed components.

ArgusAgent(config; "heartbeat_timeout" seconds, default 5): health_check();
update_heartbeat(source) records the current time; is_missing_heartbeat(source) is True if
none was recorded or the last is older than the timeout; update_signature(source, version)
stores a version; signature_changed(source, new_version) is True when it differs from the
stored one.
State: in memory only (self.last_heartbeat, self.signatures), lost on restart.
Failure: an unknown source counts as a missing heartbeat, and as changed on its first
signature check; nothing raises or alerts, callers must act on the booleans.

## Class `ArgusAgent`

- `__init__(config)`
- `health_check()`
- `update_heartbeat(source)`
- `is_missing_heartbeat(source)`
- `update_signature(source, version)`
- `signature_changed(source, new_version)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_argus.py`
