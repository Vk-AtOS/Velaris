# SIGNED_AUDIT_CHAIN

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SIGNED_AUDIT_CHAIN/main.py` (66 lines)

## Purpose

_No module docstring yet._

## Class `SignedAuditChain`

- `__init__()`
- `append_event(actor, action, details)`
- `verify_chain()`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_private_files.py`, `velaris/tests/test_signed_audit_chain.py`
