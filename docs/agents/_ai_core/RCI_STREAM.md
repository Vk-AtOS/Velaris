# RCI_STREAM

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/RCI_STREAM/main.py` (67 lines)

## Purpose

RCI_STREAM: durable, append-only event streams with offsets.

RCI is read here as "running context ingestion": events arrive on a topic
(RCI_STREAM), a bounded context is built from the latest of them
(RCI_CONTEXT), and RCI_CORE screens events on the way in.

publish(topic, event) appends one JSON line to the topic's owner-only file
under this agent's state directory and returns the event's offset (1, 2, ...).
read(topic, after=n) returns events with a higher offset, so a reader that
remembers its last offset never misses or repeats an event, across restarts.
ponytail: one file per topic, read in full; add segment files and an index
when a topic passes a few hundred thousand events.

## Class `RCI_STREAMAgent`

- `health_check()`
- `publish(topic, event)`
- `read(topic, after, limit)` — Events with offset > after, oldest first, at most `limit`.
- `topics()`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.filelock`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `RCI_CONTEXT`, `RCI_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_rci.py`, `velaris/tests/test_kan95_core.py`, `velaris/tests/test_layer23_rci.py`
