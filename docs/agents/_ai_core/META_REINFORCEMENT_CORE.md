# META_REINFORCEMENT_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/META_REINFORCEMENT_CORE/main.py` (69 lines)

## Purpose

META_REINFORCEMENT_CORE: picks between options from their recorded outcomes (UCB1 bandit).

The only "reinforcement" here is a multi-armed bandit. record(context, option,
reward) stores how well an option worked (reward 0..1). optimize() chooses
among the offered options: one never tried in this context first (in the
order offered), otherwise the highest UCB1 score

    mean reward + sqrt(2 * ln(total trials) / trials of this option)

so options with little evidence still get tried. Deterministic for a given
history. Counts are stored under this agent's state directory.

## Class `MetaReinforcementCore`

- `__init__(name)`
- `health_check()`
- `record(context, option, reward)` — Store one outcome. reward is 0 (failed) .. 1 (fully worked).
- `optimize(aligned)` — Choose from aligned["options"] for aligned["context"] (default "default").

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/META_REINFORCEMENT_CORE/outcomes.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_neuralgov.py`, `velaris/tests/test_layer5_neuralgov.py`
