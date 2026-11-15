# FAILPATH_CONTROL_ENGINE

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/FAILPATH_CONTROL_ENGINE/main.py` (58 lines)

## Purpose

Failpath control engine: maps failure codes to handler names and records each routed failure.

FailpathControlEngine: register_handler(code, action) stores a handler name (False if the
code is already registered); get_handler(code) returns it or "UNHANDLED"; route_failure(
code, context) appends {code, handler, context} to the history and returns it;
list_handlers(); list_history(). It records the routing only and never calls a handler.
State: in memory only (self.handlers, self.history), lost on restart; history grows
without bound.
Failure: an unregistered code is routed as "UNHANDLED" rather than raising.

## Class `FailpathControlEngine`

Velaris Failpath Control Engine
- Manages controlled shutdown paths
- Routes failures to safe handlers
- Tracks failure history

- `__init__()`
- `register_handler(code, action)` — code = failure identifier
- `get_handler(code)`
- `route_failure(code, context)`
- `list_handlers()`
- `list_history()`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_a.py`
