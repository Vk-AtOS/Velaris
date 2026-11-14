# CONTROL_LAYER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CONTROL_LAYER/main.py` (47 lines)

## Purpose

CONTROL_LAYER: narrow, scripted work in files, a terminal or a browser, logged and mostly reversible.

Thin wrapper over velaris.control, where the logic and its tests live. Who is acting comes only
from the Caller that the entry point set (never from an argument). Starting a run and undoing one
are `act` methods in the HTTP allowlist; the richer API (observations, approvals, kill) is /control.

## Class `CONTROL_LAYERAgent`

- `health_check()`
- `list_tasks()`
- `run_state(run_id)`
- `run_report(run_id)`
- `start_run(task_id, params)`
- `undo(run_id)`

## Depends on

- `velaris.control.service`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_control_api.py`
