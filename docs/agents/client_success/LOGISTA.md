# LOGISTA

- **Department:** `client_success`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/client_success/LOGISTA/main.py` (57 lines)

## Purpose

Logista: matches available resources to demand and picks the cheapest route.

allocate_resources(resources, demand) returns, for each demanded key, min(available, demanded) units (0 when the resource
is absent); it does not split scarce stock between competing demands, since each key is independent. choose_route(routes)
takes {route_name: cost} and returns the lowest-cost name, or None when routes is empty. health_check() returns status ok.
A stateless, rule-based helper: keeps no state. allocate_resources raises ValueError unless both arguments map names to
finite numbers of zero or more; choose_route ignores costs that are not finite numbers and returns None when none is usable.

## Class `LogistaAgent`

- `__init__(config)`
- `health_check()`
- `allocate_resources(resources, demand)` — Match available resources to demand.
- `choose_route(routes)` — Pick the cheapest route.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan85_70_finance_supply.py`, `velaris/tests/test_logista.py`
