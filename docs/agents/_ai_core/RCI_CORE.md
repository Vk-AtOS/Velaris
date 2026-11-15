# RCI_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/RCI_CORE/main.py` (66 lines)

## Purpose

RCI_CORE: the way events get into the running context, and the way the context is read.

ingest(topic, event) screens the event before it is stored: text that looks
like an attempt to instruct a model is refused (velaris.intel.guard.scan),
and secrets and personal identifiers in text values are masked. What passes
is appended to the topic through RCI_STREAM. context(topic) returns the
bounded context built by RCI_CONTEXT.

## Class `RCI_COREAgent`

- `__init__()`
- `health_check()`
- `ingest(topic, event)` — Screen, mask and store one event. Returns its offset, or why it was refused.
- `context(topic, **options)` — The current context of a topic (see RCI_CONTEXT.build for the options).

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.RCI_CONTEXT.main`
- `velaris.agents.RCI_STREAM.main`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `RCI_STREAM`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_rci.py`, `velaris/tests/test_layer23_rci.py`
