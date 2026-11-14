# NEURAL_CONSTRAINT_FIELD

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/NEURAL_CONSTRAINT_FIELD/main.py` (39 lines)

## Purpose

NEURAL_CONSTRAINT_FIELD: evaluates declared constraints over a proposed action.

Not a neural network and not a field. constrain(action, constraints) checks
the action against each constraint (a rule object, see
velaris.agentkit.aicore_b_rules) and returns every violated one. Constraints
come from the call, or from the action's own "constraints" key. With no
constraints the action is not "satisfied": nothing was checked.

## Class `NeuralConstraintField`

- `__init__(name)`
- `health_check()`
- `constrain(corrected, constraints)` — Returns satisfied, and the violated constraints with the conditions that failed.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_neuralgov.py`, `velaris/tests/test_layer5_neuralgov.py`
