# DOMAIN_SCOUT

- **Department:** `sales`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/sales/DOMAIN_SCOUT/main.py` (41 lines)

## Purpose

DOMAIN_SCOUT: find public sources about a sales vertical the company is considering.

"Domain" in the DOMAIN_* agents means a sales vertical: an industry the company
sells to (healthcare, logistics, textiles ...). scout() turns a named vertical
and region into a few search queries, runs them through the guarded web search
and returns the results with their URLs and the query that found each.

It returns sources to read, not conclusions: no market size, no ranking, and
nothing that the search did not return. No vertical -> `needs_data`.

## Class `DOMAIN_SCOUTAgent`

- `__init__()`
- `health_check()`
- `scout(vertical, region, search_fn, limit)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_sales_stubs.py`, `velaris/tests/test_layer20_adme.py`
