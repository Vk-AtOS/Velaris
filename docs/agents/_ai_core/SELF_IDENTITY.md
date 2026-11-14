# SELF_IDENTITY

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/SELF_IDENTITY/main.py` (52 lines)

## Purpose

SELF_IDENTITY: who this Velaris installation is, as a recorded, versioned fact sheet.

Keys such as name, organisation, region and owner, each a short string. A
random instance_id is assigned on first use and can never be changed, so logs
and messages from this installation can be told apart from another's. Every
change is recorded with who made it (velaris.agentkit.aicore_b_versioned): the
current caller (velaris.core.access), who must be a governance admin;
stored owner-only under this agent's state directory; survives restart.

## Class `SELF_IDENTITYAgent`

- `__init__()`
- `identity()`
- `health_check()`
- `get_identity()`
- `set_identity(key, value, by)` — True when the value was stored (or already held); False for a bad value, a frozen key, or a
- `history(key)`

## Depends on

- `velaris.agentkit.aicore_b_versioned`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_self.py`, `velaris/tests/test_layer3_selfidentity.py`
