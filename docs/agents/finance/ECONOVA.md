# ECONOVA

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/ECONOVA/main.py` (56 lines)

## Purpose

Econova: elasticity-based market sensitivity, demand projection and macro index (simple arithmetic).

EconovaAgent(config; "elasticity" default 1.0, "version"): health_check();
market_sensitivity(price_change) = elasticity * price_change; demand_projection(base_demand,
price_change) = base_demand * (1 - elasticity * price_change), which can go negative;
macro_index(metrics) = mean of the metric values.
State: keeps no state beyond the configured elasticity.
Failure: macro_index returns 0.0 for an empty dict; non-numeric inputs raise TypeError.

## Class `EconovaAgent`

- `__init__(config)`
- `health_check()`
- `market_sensitivity(price_change)` — Sensitivity = elasticity * price_change
- `demand_projection(base_demand, price_change)` — demand = base_demand * (1 - elasticity * price_change)
- `macro_index(metrics)` — Macro index = average of input macro metrics

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `AEIL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_econova.py`
