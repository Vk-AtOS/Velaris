# BUDGET_GUARDRAILS

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/BUDGET_GUARDRAILS/main.py` (70 lines)

## Purpose

_No module docstring yet._

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
