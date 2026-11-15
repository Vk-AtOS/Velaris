# SELF_HISTORY

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/SELF_HISTORY/main.py` (41 lines)

## Purpose

Self history: a small persisted event log for the system's own activity.

record(event) appends a JSON-serialisable dict and returns True; anything else is refused with a logged warning and
returns False. last() returns the most recent event, or {} when empty; the events property returns them all;
health_check() reports status ok.
State: <VELARIS_DATA>/agents/SELF_HISTORY/events.json (owner-only, atomic, shared by workers, kept across restarts);
only the newest 1000 events are kept. No caller check is made.

## Class `SELF_HISTORYAgent`

- `__init__()`
- `health_check()`
- `events()`
- `record(event)`
- `last()`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan95_core.py`, `velaris/tests/test_layer3_selfidentity.py`
