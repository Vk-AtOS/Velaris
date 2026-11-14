# PRICING_OPTIMIZER

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/PRICING_OPTIMIZER/main.py` (40 lines)

## Purpose

PRICING_OPTIMIZER: the dictionary-in, dictionary-out front for PRICING_OPTIMIZER_ENGINE.

All pricing logic lives in the engine; this agent only reads a plain payload
(as an API or workflow step would send), checks its shape, and delegates:

  {"product_id", "unit_cost", "points": [[price, qty], ...], "min_price"?, "max_price"?}
      -> PricingOptimizerEngine.optimize_from_demand   (fit a demand line, maximise profit)
  {"product_id", "unit_cost", "elasticity", "min_price"?, "max_price"?}
      -> PricingOptimizerEngine.optimize               (inverse-elasticity rule)

## Class `PRICING_OPTIMIZERAgent`

- `__init__(name)`
- `health_check()`
- `optimize(payload)`

## Depends on

- `velaris.agentkit`
- `velaris.agents.PRICING_OPTIMIZER_ENGINE.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `PRICING_OPTIMIZER_ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`, `velaris/tests/test_layer14_aeil.py`
