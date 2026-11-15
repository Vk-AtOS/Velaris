# OPS_REPORT

- **Department:** `operations`
- **Status (static inventory):** `real`
- **Source:** `departments/operations/OPS_REPORT/main.py` (155 lines)

## Purpose

OPS_REPORT — Velaris BOS agent for Knackforge
Ported from VKatOS ops_report. Daily operations report with categories, blockers, and export.

## Class `OpsReport`

- `__init__(company, db_path)`
- `log(category, item, value, member)`
- `add_blocker(description, owner)`
- `resolve_blocker(blocker_id)`
- `generate(date)`
- `generate_dict(date)`

## Class `OpsReportAgent`

Daily ops report — log entries by category, track blockers, generate text or dict reports.
Ported from VKatOS ops_report.

- `__init__(config)`
- `health_check()`
- `log(category, item, value, member)`
- `add_blocker(description, owner)`
- `resolve_blocker(blocker_id)`
- `generate_report(date)`
- `generate_report_dict(date)`

## Depends on

- `velaris.core.sqlite_util`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_no_state_in_source_tree.py`
