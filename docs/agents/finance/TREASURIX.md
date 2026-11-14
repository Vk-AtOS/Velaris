# TREASURIX

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/TREASURIX/main.py` (56 lines)

## Purpose

_No module docstring yet._

## Class `TreasurixAgent`

- `__init__(config)`
- `health_check()`
- `project_cashflow(inflows, outflows)` — Project net cashflow over the provided periods.
- `runway_months(monthly_burn, reserves)` — Compute runway in months given monthly burn and current reserves.
- `reserve_ratio(liquid_assets, short_term_liabilities)` — Simple reserve ratio = liquid_assets / short_term_liabilities

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_treasurix.py`
