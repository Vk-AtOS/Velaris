# FINANCIAL_AI_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/FINANCIAL_AI_ENGINE/main.py` (54 lines)

## Purpose

Financial AI engine: growth, a straight-line forecast and a threshold health label (plain arithmetic, no model).

compute_growth(previous, current) returns the percent change, or None when previous is zero or negative (growth is
undefined there; 0.0 would read as "no growth"). forecast_linear(data) fits a least-squares line through the values in
order and returns the next point (the value itself for a single item, 0.0 for an empty list). financial_health(revenue,
expenses, debt) scores revenue - expenses - 0.2 * debt and returns "EXCELLENT" (above 50000), "GOOD" (above 10000),
"FAIR" (above 0) or "POOR".
State: keeps none. Failure: no input validation; non-numeric values raise TypeError.

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
