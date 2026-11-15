# ASEL_STRATEGIST

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ASEL_STRATEGIST/main.py` (71 lines)

## Purpose

ASEL strategist: picks one option from several by weighted multi-criteria scoring.

Options that break a hard constraint or lack a criterion value are excluded
with the reason. The rest are scored per criterion on a 0..1 scale (min-max
across the eligible options, inverted for "min" criteria), multiplied by the
criterion weight and summed. The result shows each criterion's contribution, so
the choice can be explained and challenged. It is arithmetic over the numbers
supplied; it does not judge whether those numbers are right.

## Class `ASEL_STRATEGISTAgent`

- `__init__(name)`
- `health_check()`
- `choose(options, criteria, constraints)` — options: [{"name", <criterion>: number, ...}]; criteria: {name: {"weight", "direction": max|min}}.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.conditions`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ASEL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_a_asel.py`, `velaris/tests/test_layer13_asel.py`
