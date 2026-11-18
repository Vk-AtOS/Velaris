# SUPPLY_CHAIN_ENGINE

- **Department:** `supply_chain`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/supply_chain/SUPPLY_CHAIN_ENGINE/main.py` (121 lines)

## Purpose

SUPPLY_CHAIN_ENGINE: a replenishment plan by simulating a reorder-point policy.

Policy (s, S): whenever stock on hand plus stock on order is at or below the
reorder point s, order up to S = max_capacity; the order arrives lead_time_days
periods later.

  s = safety_stock + average forecast demand x lead_time_days

The engine walks the demand forecast one period (day) at a time: receive what is
due, serve demand, record any shortage (lost, not back-ordered), then review and
order. Costs are computed in decimal:

  holding cost  = holding_cost x closing stock, summed over the periods
  shortage cost = shortage_cost x units short

Opening stock defaults to S (a full store). It is a deterministic simulation of
the forecast supplied, not a forecast itself and not an optimiser.

## Class `SupplyChainInput`


## Class `SupplyChainEngine`

- `health_check()`
- `validate(sc)`
- `compute_plan(sc, opening_stock)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_supply_chain_stubs.py`, `velaris/tests/test_kan85_70_finance_supply.py`
