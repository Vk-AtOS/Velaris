# ASEL_EVALUATOR

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ASEL_EVALUATOR/main.py` (61 lines)

## Purpose

ASEL evaluator: says whether an executed plan achieved what it was for.

It combines the step outcomes from ASEL_EXECUTOR with measured results against
targets ({kpi: {"target", "direction": max|min, "tolerance"?}}). A KPI with no
measured value counts as missed. Verdict:
  met      every step done and every KPI on target
  partial  some steps done, and no KPI missed by more than its tolerance
  missed   nothing done, or a KPI missed beyond tolerance (or not measured)

## Class `ASEL_EVALUATORAgent`

- `__init__(name)`
- `health_check()`
- `evaluate(execution, targets, actuals)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ASEL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_asel.py`, `velaris/tests/test_layer13_asel.py`
