# SHORTTERM_MEMORY

- **Department:** `data_knowledge`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/data_knowledge/SHORTTERM_MEMORY/main.py` (75 lines)

## Purpose

SHORTTERM_MEMORY: bounded working memory per session.

push() appends an item to a session; only the newest `capacity` items are kept
and an item may carry a time-to-live. recent() returns what is still alive,
oldest first. The buffer is on disk, so a restart mid-conversation loses nothing.

promote() is the hand-over to long-term memory: the session's text goes to
velaris.intel.memory (via LONGTERM_MEMORY's store), which extracts durable
facts, masks secrets and supersedes outdated ones. This agent decides nothing
about what is worth keeping for good.

## Class `SHORTTERM_MEMORYAgent`

- `__init__(capacity)`
- `health_check()`
- `push(item, session, ttl_s, now)`
- `recent(n, session, now)` — The newest n live items of a session, oldest first ([] for an unknown session or a bad n).
- `clear(session)`
- `promote(session, scope, source, now)` — Send a session's text (strings, or the "text" of objects) to long-term memory under `scope`.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_data_knowledge_stubs.py`, `velaris/tests/test_memory_substrate.py`
