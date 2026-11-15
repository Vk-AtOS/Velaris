# RCI_CONTEXT

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/RCI_CONTEXT/main.py` (74 lines)

## Purpose

RCI_CONTEXT: builds a bounded "current context" from a stream of events.

build(entries) folds stream entries ({"offset", "ts", "event"}) into
  facts   the latest value of every key seen (newer events overwrite older),
          with the offset each value came from
  recent  the last `max_events` events
and then drops the oldest recent events until the whole context fits
`max_chars` of JSON, so it can be put in front of a model without overflowing
it. Events older than `ttl_seconds` are ignored. snapshot(topic) does the
same for a topic held by RCI_STREAM. Nothing is stored here: the stream is the state.

## Class `RCI_CONTEXTAgent`

- `__init__()`
- `health_check()`
- `build(entries, max_events, max_chars, ttl_seconds, now)`
- `snapshot(topic, **options)` — The context of a topic in RCI_STREAM. Options are those of build().

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agents.RCI_STREAM.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `RCI_CORE`, `RCI_STREAM`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_rci.py`, `velaris/tests/test_layer23_rci.py`
