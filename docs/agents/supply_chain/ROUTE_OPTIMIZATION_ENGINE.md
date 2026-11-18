# ROUTE_OPTIMIZATION_ENGINE

- **Department:** `supply_chain`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/supply_chain/ROUTE_OPTIMIZATION_ENGINE/main.py` (116 lines)

## Purpose

ROUTE_OPTIMIZATION_ENGINE: a round trip through every location, by a real heuristic.

Method: build a tour with nearest neighbour from the depot, then improve it with
2-opt (reverse a segment whenever that shortens the tour) until no reversal
helps. The result reports the distance of the first tour and of the improved one.

  leg cost = distance(a, b) x traffic factor of b (1.0 when none is given)

The depot is the first entry of `locations` unless `depot` names another. A
missing distance a->b falls back to b->a; if neither exists the request fails.
ponytail: a heuristic, not an exact solver (fine up to MAX_LOC = 30 stops), and
time windows are validated but NOT used: the distance matrix carries no travel
times. Add a time matrix and a windowed insertion step if windows must bind.

## Class `RouteRequest`


## Class `RouteOptimizationEngine`

- `health_check()`
- `validate(r)`
- `compute_route(r, depot)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_supply_chain_stubs.py`
