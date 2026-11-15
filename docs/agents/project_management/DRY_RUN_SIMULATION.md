# DRY_RUN_SIMULATION

- **Department:** `project_management`
- **Status (static inventory):** `real`
- **Source:** `departments/project_management/DRY_RUN_SIMULATION/main.py` (98 lines)

## Purpose

Dry-run simulation: records actions as simulated or executed without performing any side effect.
DryRunSimulation(dry_run=True).execute_action(action_name, payload) in dry-run mode logs the action as
simulated and returns {"status": "SIMULATED", ...}; in live mode it records and logs it as executed and
returns {"status": "EXECUTED", ...}. It never runs the action itself. log_action(action_name,
payload) logs a simulated entry. toggle_dry_run(val) switches the mode and read_log() returns the log.
State: <VELARIS_DATA>/agents/DRY_RUN_SIMULATION/dryrun.log (a JSON list, created as [] if absent) plus
in-memory lists for the current instance. Failure: an unreadable log is logged as a warning and
restarted on append or read as []; a failed write raises OSError. There is no caller check.

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
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan106_business_agents.py`
