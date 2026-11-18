# LONGTERM_MEMORY

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/LONGTERM_MEMORY/main.py` (71 lines)

## Purpose

Long-term memory: a persistent key-value store plus a scoped, time-aware fact memory.

put(k, v) and get(k, default=None) use a sealed JSON file (default <VELARIS_DATA>/agents/LONGTERM_MEMORY/
longterm.json; JsonState: encrypted, atomic, one locked read-modify-write per put, so two workers never lose a key);
put raises if the value is not JSON-serialisable. put needs an authenticated caller; get does not change anything.
remember(text, scope, source="") and recall(query, scope, k=5, at=None) delegate to velaris.intel.memory.MemoryStore,
which keeps durable facts, lets corrections supersede old ones and answers as of a time, and screens the text (a
blocked text is not stored). Both need an authenticated caller whose organisation owns `scope` ("<org>" or
"<org>:<anything>", velaris.core.access.may_read_scope): AccessDenied otherwise. The fact store is opened lazily.

## Class `LONGTERM_MEMORYAgent`

- `__init__(path)`
- `health_check()`
- `put(k, v)`
- `get(k, default)`
- `remember(text, scope, source)` — Keep the durable facts in `text`; corrections supersede old facts, nothing is deleted.
- `recall(query, scope, k, at)` — The k most relevant facts in `scope`, valid now or at time `at`.

## Depends on

- `velaris.agentkit.state`
- `velaris.core.access`
- `velaris.intel.memory`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `LOCAL_MEMORY_STORE`, `SHORTTERM_MEMORY`
- **platform modules:** `velaris/api/allowlist.py`, `velaris/orchestration/autonomy.py`
- **tests:** `velaris/tests/test_memory_substrate.py`, `velaris/tests/test_no_state_in_source_tree.py`, `velaris/tests/test_r3_memory_dna.py`
