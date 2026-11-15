# VMRK

- **Department:** `marketing`
- **Status (static inventory):** `real`
- **Source:** `departments/marketing/VMRK/main.py` (34 lines)

## Purpose

VMRK: signs and verifies messages with an HMAC-SHA256 key.
VMRK.sign(message) returns the base64 HMAC-SHA256 signature of the message. verify(message, signature)
returns True only when the signature matches, using a constant-time comparison; non-string input
returns False instead of raising. The signing key is 64 bytes, created owner-only on first use.
State: the key file <VELARIS_DATA>/agents/VMRK/vmrk.key. Failure: sign raises AttributeError for a
non-string message; an unreadable or unwritable key file raises from load_or_create_key. There is no
caller check.

## Class `VMRK`

- `__init__()`
- `sign(message)`
- `verify(message, signature)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_kan94_sales_marketing.py`, `velaris/tests/test_private_files.py`
