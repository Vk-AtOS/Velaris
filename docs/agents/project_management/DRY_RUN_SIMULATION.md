# DRY_RUN_SIMULATION

- **Department:** `project_management`
- **Status (static inventory):** `real`
- **Source:** `departments/project_management/DRY_RUN_SIMULATION/main.py` (71 lines)

## Purpose

Dry-run simulation: records what an action would do instead of doing it; it performs no action in either mode.

DryRunSimulation(dry_run=True): execute_action(action_name, payload) returns {"status": "SIMULATED", ...} and logs the
action as simulated while dry_run is on; with it off it returns and logs {"status": "EXECUTED", ...} but still calls
nothing, so "executed" only means "recorded as live". log_action(action_name, payload) logs a simulated entry directly;
toggle_dry_run(val) switches the mode; read_log() returns the persisted records.
State: <VELARIS_DATA>/agents/DRY_RUN_SIMULATION/dryrun.json (the newest 1000 records, owner-only, atomic, shared by
workers); actions_logged and actions_executed are per-instance lists, and the dry_run flag is per instance and not
persisted. Failure: a payload that cannot be written as JSON raises when the log is saved; no caller check is made.

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

- `velaris.agentkit.state`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_kan94_pm_agents.py`
