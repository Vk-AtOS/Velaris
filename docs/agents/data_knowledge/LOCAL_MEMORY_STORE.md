# LOCAL_MEMORY_STORE

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/LOCAL_MEMORY_STORE/main.py` (55 lines)

## Purpose

LOCAL_MEMORY_STORE: a small key-value store on this machine's disk.

put / get / delete / keys over one JSON file, written atomically and readable
by its owner only. A value may carry a time-to-live, after which get() no longer
returns it. The file lives in the agent's private data directory unless the
caller names a path.

It is a plain local store: no search, no versions, no scopes. Facts worth
recalling by meaning belong in LONGTERM_MEMORY.

## Class `LocalMemoryStore`

- `__init__(path)`
- `health_check()`
- `put(k, v, ttl_s, now)`
- `get(k, default, now)` — The stored value, or `default` if the key is absent, expired or not a string.
- `delete(k)`
- `keys(prefix, now)`

## Depends on

- `velaris.agentkit`

## State and configuration

- state file: `<VELARIS_DATA>/agents/LOCAL_MEMORY_STORE/store.json`

## Called by

- **other agents:** `SANDE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_data_knowledge_stubs.py`, `velaris/tests/test_layer7_offline.py`
