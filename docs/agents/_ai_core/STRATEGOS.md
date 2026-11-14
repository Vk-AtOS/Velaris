# STRATEGOS

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/STRATEGOS/main.py` (52 lines)

## Purpose

_No module docstring yet._

## Class `StrategosAgent`

- `__init__(config)`
- `health_check()`
- `evaluate_strategy(strategy)` — Returns a numeric score for a strategy.
- `rank_strategies(strategies)` — Takes a list of strategies, evaluates and returns them sorted by score (desc).
- `pick_best(strategies)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `SAGE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_strategos.py`
