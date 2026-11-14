# DRY_RUN_SIMULATION

- **Department:** `project_management`
- **Status (static inventory):** `real`
- **Source:** `departments/project_management/DRY_RUN_SIMULATION/main.py` (89 lines)

## Purpose

_No module docstring yet._

## Class `DryRunSimulation`

Dry-Run Simulation Mode
- Simulate actions without side-effects
- Maintain logs for simulated vs executed actions
- Provide a toggle for dry-run vs live

- `__init__(dry_run)`
- `log_action(action_name, payload)`
- `execute_action(action_name, payload)` — If dry_run is True: only simulate (log and return simulated result)
- `toggle_dry_run(val)`
- `read_log()`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`
