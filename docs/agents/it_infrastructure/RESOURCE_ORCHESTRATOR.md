# RESOURCE_ORCHESTRATOR

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/RESOURCE_ORCHESTRATOR/main.py` (90 lines)

## Purpose

RESOURCE_ORCHESTRATOR: named resource pools with hard capacity.

A pool is a countable resource (GPU slots, API calls per day, licence seats).
allocate() grants an owner a share only if the pool still has room; nothing is
ever over-committed and a refused request changes nothing. Grants survive a
restart, so capacity held by a crashed owner stays held until release().

## Class `RESOURCE_ORCHESTRATORAgent`

- `__init__(name)`
- `health_check()`
- `define_pool(pool, capacity)` — Create a pool or change its capacity (never below what is already granted). Infra admins only.
- `allocate(pool, owner, amount)`
- `release(pool, owner, amount)` — Give back `amount` of an owner's grant, or all of it when amount is omitted. The owner or an infra admin.
- `usage(pool)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs.py`, `velaris/tests/test_kan90_infra.py`, `velaris/tests/test_layer8_gro.py`
