# MCD

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/MCD/main.py` (33 lines)

## Purpose

Master Control Dashboard: a static route table and HTML shell stub.

MasterControlDashboard holds three fixed routes ("/", "/status", "/agents") mapped to the
names "dashboard", "system_status" and "agent_list", an HTML template string and a JS
boot string. render(content) substitutes content into the template, route_exists(path)
tells whether a path is in the table, and get_route_target(path) returns its name or None.
It serves nothing itself and does not call other agents.
State: keeps no state beyond those constants.
Failure: an unknown path gives False / None; render() with a non-string raises TypeError.

## Class `MasterControlDashboard`

- `__init__()`
- `render(content)`
- `route_exists(path)`
- `get_route_target(path)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_a.py`
