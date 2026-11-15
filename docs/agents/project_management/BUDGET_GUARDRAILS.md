# BUDGET_GUARDRAILS

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/BUDGET_GUARDRAILS/main.py` (84 lines)

## Purpose

Budget guardrails: per-category spending limits that refuse any spend which would exceed the limit.

BudgetGuardrails: set_limit(category, amount) is allowed only for governance admins
(velaris.core.access.check_caller, roles GOVERNANCE_ADMINS), needs a finite non-negative
amount and cannot go below what is already spent; record_spend(category, amount) adds to
the total if the category has a limit, the amount is finite and non-negative, the caller is
allowed and the total stays within the limit; remaining(category); status(category)
returns exists, limit, spent, remaining and blocked.
State: in memory only (self.limits, self.spent), lost on restart.
Failure: set_limit and record_spend return False (never raise) for bad input, an unknown
category, an unauthorised caller or an overrun; remaining() is 0.0 and status() is
{"exists": False} for an unknown category.

## Class `BudgetGuardrails`

Velaris Budget Guardrails
- Enforces spending limits
- Tracks usage
- Blocks overrun attempts

- `__init__()`
- `set_limit(category, amount)` — Set a limit. Governance admins only; not negative/NaN and never below what is already spent.
- `record_spend(category, amount)` — Return True if allowed, False if blocked.
- `remaining(category)`
- `status(category)`

## Depends on

- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan104_unauthenticated_writes.py`
