# MCD

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/MCD/main.py` (37 lines)

## Purpose

MCD (Master Control Dashboard): a fixed route table and a one-line HTML page template.

render(content) returns the template with the content inserted as escaped text (HTML in it is never interpreted).
route_exists(path) and get_route_target(path) look up the three built-in routes ("/", "/status", "/agents"); an unknown
path gives False and None. health_check() returns {"agent", "status": "ok", "routes": n}. It serves nothing itself: there
is no HTTP server and no authentication here.
State: none beyond the in-memory route dict. Nothing is raised on bad input.

## Class `MasterControlDashboard`

- `__init__()`
- `render(content)` — The page with `content` as TEXT: HTML in it is escaped, never interpreted.
- `health_check()`
- `route_exists(path)`
- `get_route_target(path)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_a.py`, `velaris/tests/test_kan89_aicore.py`
