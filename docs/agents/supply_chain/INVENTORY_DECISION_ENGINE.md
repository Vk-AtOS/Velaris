# INVENTORY_DECISION_ENGINE

- **Department:** `supply_chain`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/supply_chain/INVENTORY_DECISION_ENGINE/main.py` (114 lines)

## Purpose

INVENTORY_DECISION_ENGINE: reorder point, safety stock and order quantity for one item.

Textbook formulas, with the units they assume stated in the result:
  safety stock   SS  = z x sigma_d x sqrt(L)     sigma_d = sqrt(daily demand variance),
                                                 L = lead time in days,
                                                 z = normal quantile of the service level
  reorder point  ROP = d x L + SS                d = average daily demand
  order quantity EOQ = sqrt(2 x D x S / H)       D = d x 365, S = cost per order,
                                                 H = holding cost per unit per year
EOQ and ROP are capped at max_capacity. Quantities are rounded up to whole units.

The service level is 95% by default, 99% for a `priority_item`. The other
constraint flags (perishable, fragile, bulk_item) have no defined rule and are
reported as not applied. shortage_cost is not used: the service level is given,
not derived from it.

## Class `InventoryInput`


## Class `InventoryDecisionEngine`

- `health_check()`
- `validate(i)`
- `compute(i, service_level)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_supply_chain_stubs.py`
