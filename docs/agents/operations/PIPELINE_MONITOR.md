# PIPELINE_MONITOR

- **Department:** `operations`
- **Status (static inventory):** `real`
- **Source:** `departments/operations/PIPELINE_MONITOR/main.py` (133 lines)

## Purpose

PIPELINE_MONITOR — Velaris BOS agent for Knackforge
Ported from VKatOS pipeline_monitor. Statistical risk scoring for pipeline stage durations.

## Class `PipelineMonitor`

- `__init__(db_path, config)`
- `log_stage(stage_name, duration_hours, notes)`
- `morning_briefing()`
- `dashboard()`

## Class `PipelineMonitorAgent`

Statistical pipeline stage risk monitor. Z-score based anomaly detection on durations.
Ported from VKatOS pipeline_monitor.

- `__init__(config)`
- `health_check()`
- `log_stage(stage_name, duration_hours, notes)`
- `morning_briefing()`
- `dashboard()`

## Depends on

- `velaris.core.sqlite_util`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_no_state_in_source_tree.py`
