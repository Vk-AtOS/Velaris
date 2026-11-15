# CONTEXTUAL_SELF_MODEL

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/CONTEXTUAL_SELF_MODEL/main.py` (64 lines)

## Purpose

Contextual self model: the platform's own record of facts about itself, with per-context overrides.

update() stores facts (name, deployment, enabled modules, limits ...), either
as base facts or under a named context such as a tenant or an environment;
snapshot() returns the base facts with a context's overrides applied and says
which keys were overridden. A value of None removes a fact. Changes are logged.
It is a small configuration register; it does not model or infer anything.
State: <VELARIS_DATA>/agents/CONTEXTUAL_SELF_MODEL/state.json.

## Class `CONTEXTUAL_SELF_MODELAgent`

- `__init__()`
- `health_check()`
- `update(data, context, now)`
- `snapshot(context)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CONTEXTUAL_SELF_MODEL/state.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_ops.py`, `velaris/tests/test_alias_layers.py`, `velaris/tests/test_layer3_selfidentity.py`
