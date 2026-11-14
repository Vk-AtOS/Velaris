# DOMAIN_MASTERY

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/DOMAIN_MASTERY/main.py` (41 lines)

## Purpose

DOMAIN_MASTERY: how the company actually performs in each sales vertical.

"Mastery" is measured, not claimed: from the deal records supplied, per vertical,
  win rate = won / (won + lost), won revenue and its share, average won deal,
  median days from open to close of won deals.
A vertical counts as `established` only with at least `min_closed` closed deals;
below that its rates are shown but marked as too small a sample to rely on.

## Class `DOMAIN_MASTERYAgent`

- `__init__()`
- `health_check()`
- `assess(deals, min_closed)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_sales_stubs.py`, `velaris/tests/test_layer20_adme.py`
