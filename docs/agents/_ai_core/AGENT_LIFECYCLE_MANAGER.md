# AGENT_LIFECYCLE_MANAGER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/AGENT_LIFECYCLE_MANAGER/main.py` (75 lines)

## Purpose

Agent lifecycle manager: the state machine for every agent's operational state.

States: registered, active, idle, suspended, error, retired. Only the listed
transitions are accepted (a retired agent stays retired; an agent in error must
be reactivated, suspended or retired), and each accepted change is kept with
its time and reason. AGENT_LIFECYCLE is a thin front for this class.
State: <VELARIS_DATA>/agents/AGENT_LIFECYCLE_MANAGER/state.json.

## Class `LifecycleManager`

- `__init__(config)`
- `health_check()`
- `states()` — {agent: {"state": ...}} for every agent seen (read-only view).
- `set_state(agent_name, state, reason, now)` — Returns ok=True with the new state, or ok=False with the unchanged state and why.
- `get_state(agent_name)`
- `history(agent_name)`
- `list_agents(state)` — Agent names, optionally only those in one state.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/AGENT_LIFECYCLE_MANAGER/state.json`

## Called by

- **other agents:** `AGENT_LIFECYCLE`, `COGNITIVE_LOAD_BALANCER`, `ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_ops.py`
