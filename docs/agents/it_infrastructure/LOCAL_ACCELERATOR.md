# LOCAL_ACCELERATOR

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/LOCAL_ACCELERATOR/main.py` (93 lines)

## Purpose

LOCAL_ACCELERATOR: an on-disk result cache that makes repeated work instant.

Not hardware acceleration. compute(key, fn) returns the stored result for `key`
while it is fresh and otherwise calls fn(), stores what it returned and returns
that. Entries expire after their TTL, and when the cache holds more than
MAX_ENTRIES the least recently used are dropped. The cache survives restarts.

Values must be JSON. A failing fn() is reported and nothing is cached, so an
error is never served as a result.

## Class `LOCAL_ACCELERATORAgent`

- `__init__(name)`
- `health_check()`
- `get(key, now)`
- `put(key, value, ttl_s, now)`
- `compute(key, fn, ttl_s, now)` — The cached value for `key`, or fn()'s result (cached for ttl_s) if there is none.
- `stats()`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/LOCAL_ACCELERATOR/cache.json`

## Called by

- **other agents:** `SANDE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer9_compute.py`
