# VPSE_SCENARIO

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/VPSE_SCENARIO/main.py` (141 lines)

## Purpose

VPSE_SCENARIO: recomputes outcomes under what-if changes to their drivers.

run(base, formulas, scenarios):
  base       driver values, e.g. {"price": 100, "units": 50, "cost": 3000}
  formulas   outcomes as arithmetic over drivers and other outcomes, e.g.
             {"revenue": "price * units", "profit": "revenue - cost"}
  scenarios  [{"name": "price cut", "changes": {"price": {"pct": -10}, "units": {"pct": 15}}}]
             a change is {"pct": n}, {"add": n} or {"set": n}

Formulas are parsed, not executed: only numbers, names, + - * / ** %,
parentheses and min / max / abs / round are accepted, so a formula cannot run
code. They are evaluated in dependency order; a formula that refers to itself
through others is an error. Each scenario returns its outcomes and the change
against the base case; a scenario whose arithmetic fails (say, a division by
zero it causes) is reported as an error without hiding the others.

## Class `FormulaError`


## Class `VPSE_SCENARIOAgent`

- `health_check()`
- `run(base, formulas, scenarios)`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `VPSE_CORE`, `VPSE_MODELER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_vpse.py`, `velaris/tests/test_layer30_vpse.py`
