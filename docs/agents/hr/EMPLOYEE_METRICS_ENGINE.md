# EMPLOYEE_METRICS_ENGINE

- **Department:** `hr`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/hr/EMPLOYEE_METRICS_ENGINE/main.py` (227 lines)

## Purpose

Employee metrics engine: aggregates Zoho People, Payroll and Projects data into a per-employee profile, a ranked team scorecard and an org heatmap.

EmployeeMetricsEngine(config): health_check() reports the three connectors' status;
get_employee_profile(employee_id, month=None, year=None, caller=None) returns attendance,
leave, performance summary, payroll (gross, net, statutory) and project delivery for the
month (default: current); get_team_scorecard(employee_ids, month, year, caller) ranks by
composite = attendance_pct*0.30 + delivery completion*0.50 + latest appraisal score*20
(capped at 100)*0.20, using no pay data; an employee with a missing, withheld or failed component is listed last as unranked
(composite_score None, `missing` names the parts), never scored 0; get_org_heatmap(...) buckets attendance, delivery
and hours (avg, min, max, count under 70), lists the top 3 and composites under 60.
State: keeps no state; all data is fetched from the connectors on each call.
Failure: each section is fetched separately; AccessDenied from a connector becomes
{"withheld": reason} and any other error is logged and becomes {"error": message}, so a
profile is still returned. Pay access is decided by velaris.core.access in the payroll
connector.

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
- `get_team_scorecard(employee_ids, month, year, caller)` — Returns ranked scorecard for a list of employees.
- `get_org_heatmap(employee_ids, month, year, caller)` — Returns org-level heatmap data: attendance distribution, delivery health, hours. (It reads no pay: there is no payroll total.)

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
