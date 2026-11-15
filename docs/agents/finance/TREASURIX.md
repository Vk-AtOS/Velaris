# TREASURIX

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/TREASURIX/main.py` (64 lines)

## Purpose

Treasurix: treasury arithmetic (cashflow, runway, reserve ratio).

project_cashflow(inflows, outflows) returns the net sum and raises ValueError when the lists
differ in length; runway_months(monthly_burn, reserves=None) is reserves/burn (config
"initial_reserves", default 0, when reserves is omitted) and float inf when burn <= 0;
reserve_ratio(liquid_assets, short_term_liabilities) divides the two and returns inf when
liabilities are 0. Plain formulas, no forecasting. Keeps no state beyond the starting reserves.

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
