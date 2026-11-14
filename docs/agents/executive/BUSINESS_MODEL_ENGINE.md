# BUSINESS_MODEL_ENGINE

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/BUSINESS_MODEL_ENGINE/main.py` (91 lines)

## Purpose

BUSINESS_MODEL_ENGINE: revenue-model analysis of the revenue streams the caller supplies.

For streams [{"name", "kind": recurring | project | one_off, "revenue", "direct_cost",
"customer"?}] the engine computes, in decimal:

  share of revenue and gross margin per stream, and overall
  recurring share            = recurring revenue / total revenue
  customer concentration     = Herfindahl-Hirschman index, sum of (customer share %)^2,
                               0-10000 (10000 = one customer), and the largest customer's share

It describes the model as the numbers stand. It does not judge it or forecast.

## Class `BUSINESS_MODEL_ENGINEAgent`

- `__init__(name)`
- `health_check()`
- `analyze(streams)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_executive_stubs.py`, `velaris/tests/test_layer14_aeil.py`
