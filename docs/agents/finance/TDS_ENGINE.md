# TDS_ENGINE

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/TDS_ENGINE/main.py` (67 lines)

## Purpose

TDS_ENGINE: tax deducted at source under the Income-tax Act, 2025 (tax year 2026-27 onward).

  salary_tds(...)   annual tax projection and this month's deduction for one employee (s.392),
                    new regime (s.202) by default, old regime when the employee has opted. Returns
                    a person's tax figures, so the caller is checked first (velaris.core.access,
                    category "pay": the employee themself, or payroll/HR admin).
  vendor_tds(...)   deduction on a payment to a resident contractor or professional (s.393(1)
                    Table Sl. No. 6(i) and 6(iii)).

Why finance and one agent for both: deducting and depositing TDS is the employer's tax
obligation, and both computations read the same Act, Finance Act and Rules, so they share one
dated registry (statutory.py). PAYROLL_ENGINE takes the monthly figure as its `tds` input.

Every figure is in statutory.py with its source. A result with status "needs_review" carries
no tax amount and says why. These figures need an accountant's check before use.

## Class `TdsEngine`

- `__init__(config)`
- `health_check()`
- `salary_tds(employee_id, salary, regime, declarations, age_band, resident, city, proof_mode, tds_deducted_so_far, remaining_payments, tax_year, caller)` — salary         annual projected figures for the tax year (INR): basic (incl. DA), hra, other_salary
- `vendor_tds(nature, payee_type, amount, paid_before, tds_before, pan_available, payee_resident, tax_year)`

## Depends on

- `velaris.agents.TDS_ENGINE`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `departments/finance/TDS_ENGINE/salary.py`, `departments/finance/TDS_ENGINE/vendor.py`, `departments/hr/PAYROLL_ENGINE/registry.py`, `velaris/agentkit/onboarding_retention.py`
- **tests:** `velaris/tests/test_tds_engine.py`
