# MACRO_ECON_MODEL

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/MACRO_ECON_MODEL/main.py` (80 lines)

## Purpose

MACRO_ECON_MODEL: standard derived indicators from macro figures the caller supplies.

  misery index        = inflation % + unemployment %            (Okun)
  real interest rate  = ((1 + nominal) / (1 + inflation) - 1)   (Fisher, exact form), in %
  fiscal stance label = deficit (positive) or surplus (negative) as supplied

It is a calculator, not a forecasting model: it holds no economic data, fetches
none and predicts nothing. Pass `sources` so the figures stay traceable; the
result says when none were given. There is no composite "index" or tier: the
earlier one had no defined meaning.

## Class `MacroInput`


## Class `MacroEconModel`

- `health_check()`
- `validate(m)`
- `compute_index(m, sources)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`, `velaris/tests/test_engine.py`
