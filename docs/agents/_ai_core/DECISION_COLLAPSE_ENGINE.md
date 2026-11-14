# DECISION_COLLAPSE_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/DECISION_COLLAPSE_ENGINE/main.py` (46 lines)

## Purpose

Decision collapse engine: reduces several scored options to one decision, or says it cannot.

collapse() takes options ({"name", "score", "probability"?}), ranks them by
expected value (score x probability) and returns the top one. When the lead
over the runner-up is not greater than `min_margin` the result is "undecided"
and names the contenders, so a near-tie goes to a person instead of being
settled by ordering.

## Class `DecisionCollapseEngine`

- `__init__(name, min_margin)`
- `health_check()`
- `collapse(hyper)` — hyper: a list of options, or an object with an "options" list.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_aiie.py`, `velaris/tests/test_layer6_quantum.py`
