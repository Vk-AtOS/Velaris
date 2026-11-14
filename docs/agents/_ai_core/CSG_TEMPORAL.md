# CSG_TEMPORAL

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CSG_TEMPORAL/main.py` (51 lines)

## Purpose

CSG temporal: checks that a sequence of timestamped events is consistent in time.

check() takes events ({"id", "ts"}) in the order they were received and
reports: events that arrived out of order, repeated ids, events stamped further
in the future than the allowed clock skew, and gaps longer than `max_gap`.
It returns the ids in time order. It reports problems; it does not repair them.

## Class `CSG_TEMPORALAgent`

- `__init__(max_skew)`
- `health_check()`
- `check(events, max_gap, now)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `COHERENCE_SYNC_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_csg.py`, `velaris/tests/test_layer28_csg.py`
