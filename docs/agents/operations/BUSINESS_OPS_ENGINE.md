# BUSINESS_OPS_ENGINE

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/BUSINESS_OPS_ENGINE/main.py` (71 lines)

## Purpose

Business ops engine: a minimal in-memory task list and KPI table.

add_task(name, params) appends a PENDING task (and returns a copy of it); complete_task(name) marks the first PENDING task
with that name DONE and returns True, or False if none is pending (completing twice completes two tasks, not one twice).
list_tasks() returns deep copies. set_kpi(key, value) and get_kpi(key) store and read finite numbers (0.0 for an unknown
key). summarize() returns total, completed, pending and the KPIs. It runs nothing and schedules nothing, so
"orchestration" here is bookkeeping only. State: in memory, lost on exit. A bad name, params or value raises ValueError;
at most 10,000 tasks and 1,000 KPIs.

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
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_r3_ops.py`
