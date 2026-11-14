# FLEET_HEALTH_ENGINE

- **Department:** `supply_chain`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/supply_chain/FLEET_HEALTH_ENGINE/main.py` (132 lines)

## Purpose

FLEET_HEALTH_ENGINE: a vehicle's condition from its usage, wear and service records.

Explicit rules, each reported with the reading that triggered it:
  * an active fault code maps to an action in FAULT_ACTIONS; a brake or engine fault takes
    the vehicle out of service;
  * a wear reading at or past its limit in WEAR_LIMITS asks for replacement, within 10
    points of it asks for inspection (battery_health is the other way round: low is bad);
  * service is due when distance since the last service reaches the interval. The interval
    is the manufacturer's and must be supplied; without it the service check is `needs_data`.

condition: out_of_service > attention > serviceable. The limits are this engine's
defaults (percent worn), not a manufacturer's schedule; pass `wear_limits` to override.
There is no composite health score.

## Class `VehicleStatus`


## Class `FleetHealthEngine`

- `health_check()`
- `validate(v)`
- `assess(v, last_service_km, service_interval_km, wear_limits)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_supply_chain_stubs.py`
