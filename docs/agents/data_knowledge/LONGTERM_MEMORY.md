# LONGTERM_MEMORY

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/LONGTERM_MEMORY/main.py` (49 lines)

## Purpose

_No module docstring yet._

## Class `LONGTERM_MEMORYAgent`

- `__init__(path)`
- `health_check()`
- `put(k, v)`
- `get(k, default)`
- `remember(text, scope, source)` — Keep the durable facts in `text`; corrections supersede old facts, nothing is deleted.
- `recall(query, scope, k, at)` — The k most relevant facts in `scope`, valid now or at time `at`.

## Depends on

- `velaris.intel.memory`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `LOCAL_MEMORY_STORE`, `SHORTTERM_MEMORY`
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_memory_substrate.py`
