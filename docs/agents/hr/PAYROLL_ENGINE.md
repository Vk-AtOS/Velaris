# PAYROLL_ENGINE

- **Department:** `hr`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/hr/PAYROLL_ENGINE/main.py` (304 lines)

## Purpose

_No module docstring yet._

## Class `_Run`

One employee-month: looks parameters up by date and records what was used and what is unresolved.

- `__init__(start, end)`
- `param(name, on)`
- `warnings()`

## Class `PayrollEngine`

India statutory payroll computation engine (Tamil Nadu scope).
Wraps Zoho Payroll for live data; also does local computation
from raw salary components when Zoho credentials are unavailable.

Every statutory number comes from statutory.py by the pay period's date.
A result whose "status" is "needs_review" has None for each amount that
could not be established (and for every total that depends on it) and
says why in "review_reasons". Never pay from such a result.

- `__init__(config)`
- `health_check()`
- `compute(employee_id, basic, hra, special_allowance, tds, pay_period, local_body, half_year_gross, epf_basis)` — Compute one month's take-home from salary components.
- `compute_bulk(employees, pay_period)` — employees: [{"employee_id": ..., "basic": ..., "hra": ..., "special_allowance": ..., "tds": ...,
- `org_statutory_summary(employees, pay_period)` — Aggregates EPF/ESI/PT obligations across the org for one month.
- `get_payslip(employee_id, year, month, caller)`
- `get_statutory_deductions(employee_id, year, month, caller)`
- `get_ytd_summary(employee_id, financial_year, caller)`

## Depends on

- `velaris.agents.PAYROLL_ENGINE`
- `velaris.agents.ZOHO_PAYROLL.main`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `GST_ENGINE`, `OFFER_LETTERS`, `TDS_ENGINE`
- **platform modules:** `departments/finance/GST_ENGINE/statutory.py`, `departments/finance/TDS_ENGINE/salary.py`, `departments/finance/TDS_ENGINE/statutory.py`, `departments/finance/TDS_ENGINE/vendor.py`, `departments/hr/PAYROLL_ENGINE/registry.py`, `departments/hr/PAYROLL_ENGINE/statutory.py`, `velaris/agentkit/onboarding_checklists.py`, `velaris/agentkit/onboarding_offer_math.py`, `velaris/agentkit/onboarding_retention.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_caller_access.py`, `velaris/tests/test_onboarding_offer.py`, `velaris/tests/test_onboarding_parts.py`, `velaris/tests/test_onboarding_records.py`, `velaris/tests/test_payroll_statutory.py`, `velaris/tests/test_tds_engine.py`
