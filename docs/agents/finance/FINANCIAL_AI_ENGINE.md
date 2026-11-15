# FINANCIAL_AI_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/FINANCIAL_AI_ENGINE/main.py` (46 lines)

## Purpose

_No module docstring yet._

## Class `FinancialAIEngine`

Velaris Financial AI Engine
- Computes growth
- Forecasts trends (simple linear model)
- Evaluates financial health scores

- `compute_growth(previous, current)` — Percent growth, or None when it is undefined (previous is zero or negative): 0.0 would mean "no growth".
- `forecast_linear(data)`
- `financial_health(revenue, expenses, debt)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan85_70_finance_supply.py`
