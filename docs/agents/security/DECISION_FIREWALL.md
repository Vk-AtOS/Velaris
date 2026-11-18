# DECISION_FIREWALL

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/DECISION_FIREWALL/main.py` (43 lines)

## Purpose

DECISION_FIREWALL: a persistent block list of decision keys.

block(key) adds a key; only a governance or security admin may do it (the current
caller, velaris.core.access; the decision is traced either way). allow(key) is True
only for a well-formed key that is not blocked; anything that is not a usable key
is refused (False). The list is stored owner-only under this agent's state
directory and survives restart.

## Class `DECISION_FIREWALLAgent`

- `__init__()`
- `health_check()`
- `blocked()`
- `block(key)` — Block `key`, as the current caller (a governance or security admin).
- `allow(key)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/DECISION_FIREWALL/blocked.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_governance_kernel.py`
