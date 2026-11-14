# EMPLOYEE_METRICS_ENGINE

- **Department:** `hr`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/hr/EMPLOYEE_METRICS_ENGINE/main.py` (199 lines)

## Purpose

_No module docstring yet._

## Class `EmployeeMetricsEngine`

Aggregates Zoho People + Zoho Payroll + Zoho Projects data
into a unified per-employee metrics profile.
Feeds dashboard visualizations.
Pay figures are read through ZohoPayrollConnector, which asks velaris.core.access
whether the caller may see them (their own record, or a payroll/HR administrator).
When they may not, the profile carries {"withheld": reason} instead of pay; the
scorecard and heatmap never read pay at all.

- `__init__(config)`
- `health_check()`
- `get_employee_profile(employee_id, month, year, caller)` — Full unified profile for one employee.
- `get_team_scorecard(employee_ids, month, year)` — Returns ranked scorecard for a list of employees.
- `get_org_heatmap(employee_ids, month, year)` — Returns org-level heatmap data: attendance distribution, delivery health, payroll total.

## Depends on

- `velaris.agents.ZOHO_PAYROLL.main`
- `velaris.agents.ZOHO_PEOPLE.main`
- `velaris.agents.ZOHO_PROJECTS.main`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_caller_access.py`
