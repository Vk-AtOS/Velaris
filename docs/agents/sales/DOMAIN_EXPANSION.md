# DOMAIN_EXPANSION

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/DOMAIN_EXPANSION/main.py` (63 lines)

## Purpose

DOMAIN_EXPANSION: how much of each vertical's market the company has, and what is left.

Needs two things from the caller: deal records, and a market size per vertical
WITH the source it came from ({"healthcare": {"size": 50000000, "source": "..."}}).
The agent holds no market sizes and does not estimate one: without them the
result is `needs_data`.

  penetration = won revenue in the vertical / market size
  whitespace  = market size - won revenue

Verticals are listed by whitespace, largest first. Revenue and market size must
cover the same period and currency; the agent cannot check that and says so.

## Class `DOMAIN_EXPANSIONAgent`

- `__init__()`
- `health_check()`
- `assess(deals, market_sizes)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_sales_stubs.py`, `velaris/tests/test_layer20_adme.py`
