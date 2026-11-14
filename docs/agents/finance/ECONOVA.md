# ECONOVA

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/ECONOVA/main.py` (46 lines)

## Purpose

_No module docstring yet._

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
