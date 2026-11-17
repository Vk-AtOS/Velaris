# BUDGET_GUARDRAILS

- **Department:** `project_management`
- **Status (static inventory):** `real`
- **Source:** `departments/project_management/BUDGET_GUARDRAILS/main.py` (117 lines)

## Purpose

Budget guardrails: per-category spending limits in rupees, exact to the paisa, that block overruns.

set_limit(category, amount) sets a limit: governance admins only (check_caller, traced), never below what is already
spent, at most 1000 categories. record_spend(category, amount) adds to the category's total and returns True, or False
when the spend would pass the limit, the category has no limit, or there is no authenticated caller; the check and the
add are one atomic step across processes. remaining(category) returns limit minus spent as a Decimal (0.00 for an
unknown category); status(category) returns {exists, limit, spent, remaining, blocked}, or {"exists": False}. Amounts may
be int, float, Decimal or numeric text; a bool, NaN, infinity, a negative value, more than two decimals or more than 10
trillion rupees is refused with False, never raised.
State: <VELARIS_DATA>/agents/BUDGET_GUARDRAILS/budgets.json (integer paise, owner-only, shared by every worker).

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
- **tests:** `velaris/tests/test_allowlist_departments.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_kan94_pm_agents.py`
