# ALK_EVO

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/ALK_EVO/main.py` (96 lines)

## Purpose

ALK evo: champion/challenger selection between named versions of a configuration.

Variants are registered with their settings and collect scores from real use.
evaluate() promotes a challenger only when both it and the champion have at
least `min_samples` scores and its mean beats the champion's by more than
`margin`; rollback() restores the previous champion. Nothing is mutated or
generated here: people (or other code) propose variants, this agent keeps the
evidence and decides which one is in force.
State: <VELARIS_DATA>/agents/ALK_EVO/state.json.

## Class `ALK_EVOAgent`

- `__init__(min_samples, margin)`
- `health_check()`
- `register(variant, config)` — Add a variant. The first one registered becomes the champion.
- `record(variant, score)`
- `champion()`
- `evaluate()` — Promote the best qualifying challenger, if any. Returns the standings either way.
- `rollback()`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/ALK_EVO/state.json`

## Called by

- **other agents:** `REGISTRY`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_alk.py`, `velaris/tests/test_kan106_aicore.py`, `velaris/tests/test_kan95_core.py`, `velaris/tests/test_layer27_alk.py`
