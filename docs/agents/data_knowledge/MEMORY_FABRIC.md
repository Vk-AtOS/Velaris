# MEMORY_FABRIC

- **Department:** `data_knowledge`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/data_knowledge/MEMORY_FABRIC/main.py` (86 lines)

## Purpose

Memory fabric: in-process key-value memory shared between agents, with no persistence.

MEMORY_FABRICAgent offers write_bucket(bucket, data) and read_bucket(bucket) (returns {} for an unknown bucket).
MemoryFabric, a compatibility shim, offers get_store(namespace) (a dict, created on demand), put(namespace, key, value,
ttl) (ttl in seconds, None means never expires), get(namespace, key) (the value, or None if absent or expired) and
query(namespace, prefix) (unexpired {key: value}, optionally only keys starting with prefix). health_check() returns ok.
State: Python dicts in memory only; everything is lost when the process ends. It does no validation and raises nothing
on bad input beyond the normal TypeError for unhashable keys.

## Class `MEMORY_FABRICAgent`

- `__init__()`
- `health_check()`
- `write_bucket(bucket, data)`
- `read_bucket(bucket)`

## Class `MemoryFabric`

Minimal MemoryFabric compatibility shim (repair).
Provides a simple API expected by other agents:
  - health_check()
  - get_store(name) -> dict-like object
  - put(namespace, key, value, ttl=None) / get(namespace, key) / query(namespace, prefix=None)
This stub will be used only if the real MemoryFabric export is missing.

- `__init__()`
- `health_check()`
- `get_store(name)`
- `put(namespace, key, value, ttl)` — Store value under namespace/key; ttl is seconds until it expires (None = never).
- `get(namespace, key)` — The stored value, or None if absent or expired.
- `query(namespace, prefix)` — Unexpired {key: value} in a namespace, optionally only keys starting with prefix.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `NEURAL_MESH`
- **platform modules:** none found
- **tests:** `velaris/tests/test_infra_agents.py`, `velaris/tests/test_memory_substrate.py`, `velaris/tests/test_no_silent_except.py`
