# FISCALIS

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/FISCALIS/main.py` (50 lines)

## Purpose

_No module docstring yet._

## Class `FiscalisAgent`

- `__init__(config)`
- `health_check()`
- `set_budget(category, amount)`
- `get_budget(category)`
- `cost_breakdown(costs)` — Return total cost from all categories.
- `forecast_expenses(monthly_costs, growth_rate)` — Forecast next month's expenses using optional growth rate.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_aicore_a_ops.py`, `velaris/tests/test_fiscalis.py`
