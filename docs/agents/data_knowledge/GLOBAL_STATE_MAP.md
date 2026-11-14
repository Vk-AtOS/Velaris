# GLOBAL_STATE_MAP

- **Department:** `data_knowledge`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/data_knowledge/GLOBAL_STATE_MAP/main.py` (97 lines)

## Purpose

GLOBAL_STATE_MAP: one shared, versioned map of state that several agents read and write.

Every key has a version that rises by one on each write, and the whole map has
a revision that rises on every change. That gives writers and readers two
guarantees:

  set(key, value, by, expect_version=n)   compare-and-set: the write happens only
                                          if the key is still at version n, so two
                                          agents cannot silently overwrite each other
  changes(since_rev)                      everything that changed after a revision,
                                          in order, so a reader can catch up without
                                          re-reading the map

Each change records who made it: the current caller (velaris.core.access). Any
authenticated person or service may write (the map is shared coordination state, and
compare-and-set, not ownership, is what keeps writers apart); nobody may write
anonymously, and a legacy `by` argument must name that same caller. The map and its
change log are on disk; the log keeps the latest MAX_LOG changes.

## Class `GLOBAL_STATE_MAPAgent`

- `__init__(name)`
- `health_check()`
- `set(key, value, by, expect_version)` — Write a key. With expect_version, only if the key is at that version (0 = must not exist yet).
- `delete(key, by, expect_version)`
- `get(key)`
- `snapshot()`
- `changes(since_rev)` — Changes with a revision above since_rev, oldest first. `complete` is False if older ones were trimmed.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `GCK`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_data_knowledge_stubs.py`, `velaris/tests/test_layer8_gro.py`
