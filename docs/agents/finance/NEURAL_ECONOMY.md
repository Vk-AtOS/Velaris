# NEURAL_ECONOMY

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/NEURAL_ECONOMY/main.py` (93 lines)

## Purpose

NEURAL_ECONOMY: unit economics calculator. There is no neural network here.

The name is historical. What the agent does is cost-volume-profit arithmetic on
figures the caller supplies, in decimal:

  contribution margin   = price - variable cost            (per unit)
  break-even units      = fixed costs / contribution margin, rounded up
  profit at a volume    = units x contribution margin - fixed costs
  margin of safety      = (units - break-even units) / units

and, when account figures are supplied (arpa, gross_margin_pct, monthly_churn_pct, cac):

  lifetime value (LTV)  = monthly revenue per account x gross margin / monthly churn
  LTV : CAC             and CAC payback months = CAC / (monthly revenue x gross margin)

## Class `NeuralEconomyAgent`

- `__init__(config)`
- `health_check()`
- `run(payload)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_finance_stubs.py`
