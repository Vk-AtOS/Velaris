# AUDITOR

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/AUDITOR/main.py` (45 lines)

## Purpose

_No module docstring yet._

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
- **platform modules:** none found
- **tests:** `velaris/tests/test_auditor.py`
