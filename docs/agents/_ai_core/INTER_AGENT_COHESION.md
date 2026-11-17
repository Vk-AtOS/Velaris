# INTER_AGENT_COHESION

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/INTER_AGENT_COHESION/main.py` (71 lines)

## Purpose

INTER_AGENT_COHESION: a shared board where agents leave facts for each other without overwriting each other.

link(namespace, key, value, ttl, agent, expected_version) stores a value with
a version number, the writing agent and an optional expiry. When
expected_version is given the write succeeds only if the stored version still
is that number (compare-and-set), so two agents updating the same fact cannot
silently lose each other's change: the second gets "conflict" and the current
value. recall / list_namespace read current, unexpired values. Stored
owner-only under this agent's state directory; survives restart.

## Class `Cohesion`

- `__init__(config)`
- `health_check()`
- `link(namespace, key, metadata, ttl, agent, expected_version)` — Store `metadata` under namespace/key. Returns the new version, or "conflict" with the current entry.
- `entry(namespace, key)` — Value with its version, writer and time, or None.
- `recall(namespace, key)`
- `list_namespace(namespace, prefix)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/INTER_AGENT_COHESION/board.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_self.py`, `velaris/tests/test_infra_agents.py`
