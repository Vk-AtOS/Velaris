# BUSINESS_OPS_ENGINE

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/BUSINESS_OPS_ENGINE/main.py` (55 lines)

## Purpose

Business ops engine: a minimal in-memory task list and KPI table.

add_task(name, params) appends a PENDING task and returns it; complete_task(name) marks the first task with that name DONE
and returns True, or False if none matches. list_tasks() returns a copy of the list. set_kpi(key, value) and get_kpi(key)
store and read numbers (0.0 for an unknown key). summarize() returns total, completed, pending and the KPIs. It runs nothing
and schedules nothing, so "orchestration" here is bookkeeping only. State: in memory, lost on exit; no validation.

## Class `BusinessOpsEngine`

Velaris Business Ops Engine
- Task orchestration
- KPI tracking
- Automated workflow sequencing

- `__init__()`
- `add_task(name, params)`
- `complete_task(name)`
- `list_tasks()`
- `set_kpi(key, value)`
- `get_kpi(key)`
- `summarize()`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`
