# LONGTERM_MEMORY

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/LONGTERM_MEMORY/main.py` (58 lines)

## Purpose

Long-term memory: a persistent key-value store plus a scoped, time-aware fact memory.

put(k, v) and get(k, default=None) use a JSON file (default <VELARIS_DATA>/agents/LONGTERM_MEMORY/
longterm.json, written privately); an unreadable file is logged and treated as empty, and put
raises if the value is not JSON-serialisable. remember(text, scope, source="") and
recall(query, scope, k=5, at=None) delegate to velaris.intel.memory.MemoryStore, which keeps
durable facts, lets corrections supersede old ones and answers as of a time. The fact store is
opened lazily on first use. No access check is made here.

## Class `LONGTERM_MEMORYAgent`

- `__init__(path)`
- `health_check()`
- `put(k, v)`
- `get(k, default)`
- `remember(text, scope, source)` — Keep the durable facts in `text`; corrections supersede old facts, nothing is deleted.
- `recall(query, scope, k, at)` — The k most relevant facts in `scope`, valid now or at time `at`.

## Depends on

- `velaris.intel.memory`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `LOCAL_MEMORY_STORE`, `SHORTTERM_MEMORY`
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_memory_substrate.py`, `velaris/tests/test_no_state_in_source_tree.py`
