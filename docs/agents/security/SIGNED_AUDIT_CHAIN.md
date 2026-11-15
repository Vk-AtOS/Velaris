# SIGNED_AUDIT_CHAIN

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SIGNED_AUDIT_CHAIN/main.py` (111 lines)

## Purpose

Signed audit chain: tamper-evident append-only log of events, linked by hashes and signed with HMAC.
SignedAuditChain.append_event(actor, action, details) appends a signed entry holding a UTC timestamp,
actor, action, details and the hash of the previous line, under a file lock, and updates a signed
head (entry count plus last-line hash). verify_chain() returns True only if every line is signed
and linked and the signed head matches the end, so edits, reordering and truncation are detected.
State: <VELARIS_DATA>/agents/SIGNED_AUDIT_CHAIN/chain.log, chain.head and chain.key (owner-only
files; key is 64 bytes, created on first use). Failure: verify_chain never raises on bad data and
returns False; append_event raises OSError or TypeError on unwritable files or details that are not
JSON serializable, and has no caller check.

## Class `SignedAuditChain`

- `__init__()`
- `append_event(actor, action, details)`
- `verify_chain()` — True only if every line is signed and linked and the signed head matches the end. Never raises on bad data.

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan103_trace_durability.py`, `velaris/tests/test_private_files.py`, `velaris/tests/test_signed_audit_chain.py`
