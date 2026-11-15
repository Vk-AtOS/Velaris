# LOCAL_REGISTRY_CACHE

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/LOCAL_REGISTRY_CACHE/main.py` (59 lines)

## Purpose

LOCAL_REGISTRY_CACHE: an offline copy of "which agents exist and where".

refresh() scans departments/ and stores {agent: {"department": ...}} on disk, so
a lookup needs neither the network nor a full import of every agent. update()
stores a registry the caller built instead. is_stale() says when the copy is old
enough to refresh. The cache survives restarts.

## Class `LocalRegistryCache`

- `__init__(name)`
- `health_check()`
- `cache()` — The stored registry ({} when nothing has been cached).
- `update(reg)` — Replace the cached registry with `reg` ({name: JSON value}).
- `refresh()` — Rebuild the registry from the departments/ tree on this machine.
- `lookup(name)`
- `is_stale(max_age_s, now)` — True when there is no cache or it is older than max_age_s (also true for unusable arguments).

## Depends on

- `velaris`
- `velaris.agentkit`

## State and configuration

- state file: `<VELARIS_DATA>/agents/LOCAL_REGISTRY_CACHE/registry.json`

## Called by

- **other agents:** `SANDE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer7_offline.py`
