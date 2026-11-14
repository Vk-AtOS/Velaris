# ZOHO_PAYROLL

- **Department:** `_connectors`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_connectors/ZOHO_PAYROLL/main.py` (81 lines)

## Purpose

_No module docstring yet._

## Class `ZohoPayrollConnector`

Pulls payroll data from Zoho Payroll (India):
- Payslips per employee per month
- Salary components (basic, HRA, special allowance)
- Statutory deductions (EPF, ESI, TDS, PT)
- Net pay and YTD summaries

Every method returns one employee's pay, so each one first asks velaris.core.access
whether the caller (passed as `caller=`, or set with acting_as) may read it: the
employee themself, or a payroll or HR administrator. Anyone else, or no caller at
all, gets AccessDenied, and the decision is written to the trace either way.

- `__init__(config)`
- `health_check()`
- `get_payslip(employee_id, year, month, caller)` — Returns full payslip breakdown for a given month.
- `get_ytd_summary(employee_id, financial_year, caller)` — Returns year-to-date earnings, deductions, and net pay.
- `get_statutory_deductions(employee_id, year, month, caller)` — Returns EPF, ESI, TDS, Professional Tax for the month.
- `get_cost_to_company(employee_id, year, month, caller)` — Returns total CTC including employer contributions.

## Depends on

- `velaris.agents.ZOHO_CONNECTOR.main`
- `velaris.core.access`

## State and configuration

- keeps no files of its own
- env var: `ZOHO_ORG_ID`

## Called by

- **other agents:** `EMPLOYEE_METRICS_ENGINE`, `PAYROLL_ENGINE`
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_caller_access.py`
