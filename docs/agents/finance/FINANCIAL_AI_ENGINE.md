# FINANCIAL_AI_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/FINANCIAL_AI_ENGINE/main.py` (53 lines)

## Purpose

Financial AI engine: rule-based finance arithmetic, not a learned model.

compute_growth(previous, current) is percentage growth, 0.0 when previous <= 0;
forecast_linear(data) is the next value of a least-squares line (last value for one point, 0.0
for empty); financial_health(revenue, expenses, debt) scores revenue - expenses - 0.2*debt and
returns EXCELLENT (>50000), GOOD (>10000), FAIR (>0) or POOR. Fixed thresholds, no currency
handling. Keeps no state. Non-numeric input raises TypeError.

## Class `FinancialAIEngine`

Velaris Financial AI Engine
- Computes growth
- Forecasts trends (simple linear model)
- Evaluates financial health scores

- `compute_growth(previous, current)`
- `forecast_linear(data)`
- `financial_health(revenue, expenses, debt)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`
