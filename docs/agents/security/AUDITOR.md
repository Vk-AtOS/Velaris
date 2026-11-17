# AUDITOR

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/AUDITOR/main.py` (48 lines)

## Purpose

Auditor: checks a workflow against required steps and scans log lines for banned terms.

check_compliance(workflow_steps, required_steps) is True only when every required step is
present; find_violations(log_entries, banned_terms) returns the entries containing any banned
term (case-sensitive substring). Pure functions, no policy source and no audit trail: it keeps
no state. Non-iterable input raises TypeError.

## Class `AuditorAgent`

- `__init__(config)`
- `health_check()`
- `check_compliance(workflow_steps, required_steps)` — Ensure required steps are included in workflow_steps.
- `find_violations(log_entries, banned_terms)` — Returns log entries containing banned terms.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_allowlist_departments.py`, `velaris/tests/test_auditor.py`
