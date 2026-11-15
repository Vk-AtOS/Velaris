# SLA_MONITOR

- **Department:** `operations`
- **Status (static inventory):** `real`
- **Source:** `departments/operations/SLA_MONITOR/main.py` (131 lines)

## Purpose

SLA_MONITOR — Velaris BOS agent for Knackforge
Ported from VKatOS sla_monitor. Tracks client/delivery SLA commitments and surfaces breaches.

## Class `SLAMonitor`

- `__init__(db_path)`
- `add(client, description, deadline_hours, priority)`
- `close(commitment_id)`
- `scan()`
- `dashboard()`

## Class `SLAMonitorAgent`

SLA commitment tracker — add deadlines, scan for breaches, surface dashboard.
Ported from VKatOS sla_monitor.

- `__init__(config)`
- `health_check()`
- `add_commitment(client, description, deadline_hours, priority)`
- `check_breaches()`
- `resolve(commitment_id)`
- `dashboard()`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_no_state_in_source_tree.py`
