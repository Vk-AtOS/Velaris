# BUDGET_GUARDRAILS

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/BUDGET_GUARDRAILS/main.py` (106 lines)

## Purpose

_No module docstring yet._

## Class `BudgetGuardrails`

Velaris Budget Guardrails (INR, exact to the paisa)
- Enforces spending limits; tracks usage; blocks overrun attempts
- Amounts are Decimal rupees; stored as integer paise in VELARIS_DATA, so every worker sees the same totals
  and the check-and-add of a spend is one atomic, cross-process step

- `__init__()`
- `limits()`
- `spent()`
- `set_limit(category, amount)` — Set a limit. Governance admins only; not negative/NaN and never below what is already spent.
- `record_spend(category, amount)` — Return True if allowed, False if blocked.
- `remaining(category)`
- `status(category)`

## Depends on

- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/BUDGET_GUARDRAILS/budgets.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_kan94_pm_agents.py`
