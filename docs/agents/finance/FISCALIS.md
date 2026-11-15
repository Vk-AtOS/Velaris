# FISCALIS

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/FISCALIS/main.py` (54 lines)

## Purpose

Fiscalis: budget bookkeeping and basic expense arithmetic.
FiscalisAgent.set_budget(category, amount) stores float(amount) and returns True; get_budget(category)
returns it, or 0.0 for an unknown category. cost_breakdown(costs) returns the sum of the dict values.
forecast_expenses(monthly_costs, growth_rate=0.0) returns last month * (1 + growth_rate), or 0.0 for
an empty list. Plain arithmetic, not a statistical forecast.
State: the budgets live in an in-memory dict only; nothing is persisted.
Failure: a non-numeric amount raises ValueError or TypeError; nothing else is validated.

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
- **platform modules:** `velaris/api/allowlist.py`, `velaris/intel/tools.py`
- **tests:** `velaris/tests/test_aicore_a_ops.py`, `velaris/tests/test_fiscalis.py`
