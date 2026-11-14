# WAREHOUSE_FLOW_ENGINE

- **Department:** `supply_chain`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/supply_chain/WAREHOUSE_FLOW_ENGINE/main.py` (108 lines)

## Purpose

WAREHOUSE_FLOW_ENGINE: one period of warehouse flow, worked through as arithmetic.

  put away          = inbound units x putaway efficiency      (the rest waits at the dock)
  picked            = outbound units x picking efficiency     (the rest is pick backlog),
                      limited to the stock actually available
  closing stock     = opening stock + put away - picked
  utilisation       = closing stock / storage capacity
  periods until full = free space / net units stored per period, when stock is growing

Each raised congestion flag is listed with the standard first response for it,
and the engine reports where a flag disagrees with the numbers (for example
`storage_overflow` raised while utilisation is low). Efficiencies are fractions
of the period's work that gets done. There is no composite score.

## Class `WarehouseFlowInput`


## Class `WarehouseFlowEngine`

- `health_check()`
- `validate(w)`
- `assess(w, opening_stock)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_supply_chain_stubs.py`
