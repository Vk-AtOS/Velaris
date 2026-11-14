# MACHINE_LIFECYCLE_ENGINE

- **Department:** `supply_chain`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/supply_chain/MACHINE_LIFECYCLE_ENGINE/main.py` (119 lines)

## Purpose

MACHINE_LIFECYCLE_ENGINE: where a machine is in its life, from usage and maintenance records.

Computed from the record supplied (as_of_year defaults to the current year):
  age, hours per year                          operating_hours / age
  MTBF                                         operating_hours / (corrective + minor_repair events)
  preventive share                             preventive events / all maintenance events
  remaining useful life (hours and years)      expected_life_hours / load_factor - operating_hours,
                                               then / hours per year
  components due                               component age >= its life limit

`expected_life_hours` and `component_life` are the manufacturer's figures and must
be supplied; without them those parts of the result are `needs_data`. The engine
does not guess a design life and there is no composite score.

## Class `MachineLifecycleInput`


## Class `MachineLifecycleEngine`

- `health_check()`
- `validate(m, as_of_year)`
- `assess(m, expected_life_hours, component_life, as_of_year)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_supply_chain_stubs.py`
