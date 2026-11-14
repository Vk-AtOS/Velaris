# PRICING_OPTIMIZER_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/PRICING_OPTIMIZER_ENGINE/main.py` (156 lines)

## Purpose

PRICING_OPTIMIZER_ENGINE: profit-maximising price, by two stated methods.

  optimize_from_demand   observed (price, quantity) points -> least-squares line q = a + b.p,
                         then the price that maximises (p - cost)(a + b.p):
                             p* = cost/2 - a/(2b), clipped to [min_price, max_price].
                         Refuses with fewer than 3 distinct prices, or when demand does not
                         fall as price rises (b >= 0): there is nothing to optimise.
  optimize               a PricingInput with a constant price elasticity e (> 1): the inverse-
                         elasticity (Lerner) rule p* = cost . e / (e - 1). With e <= 1 profit
                         rises with price without limit, so a max_price is required.

Fitting and arithmetic are in code; no model is involved. demand_index,
competition_index, season_factor and the constraint flags of PricingInput have
no defined unit and are NOT used; the result lists them as ignored. Bounds are
passed as min_price / max_price. PRICING_OPTIMIZER delegates here.

## Class `PricingInput`


## Class `PricingOptimizerEngine`

- `health_check()`
- `validate(p)`
- `optimize(p, min_price, max_price)`
- `optimize_from_demand(product_id, unit_cost, points, min_price, max_price)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `PRICING_OPTIMIZER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`
