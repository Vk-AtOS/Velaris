# STRATEGOS

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/STRATEGOS/main.py` (63 lines)

## Purpose

Strategos: scores and ranks candidate strategies with a simple heuristic.
StrategosAgent.evaluate_strategy(strategy) returns (benefit - cost) / (1 + risk) from the numeric
fields "benefit", "cost" and "risk" (each defaults to 0). rank_strategies(strategies) returns
[{"strategy", "score"}] sorted by score descending. pick_best(strategies) returns the top item, or None
for an empty list. This is a rule-based formula, not a learned model.
State: keeps no state. Failure: a field that cannot be converted to float raises ValueError or
TypeError; a risk of -1 raises ZeroDivisionError. Nothing is caught.

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
- **tests:** `velaris/tests/test_kan95_core.py`, `velaris/tests/test_strategos.py`
