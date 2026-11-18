# STREAM_PROCESSOR

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/STREAM_PROCESSOR/main.py` (102 lines)

## Purpose

STREAM_PROCESSOR: tumbling-window aggregation over event streams.

define() declares a stream: the window length, which field holds the number to
aggregate, and optionally a field to group by. ingest() takes batches of events
({"ts": seconds, <value_field>: number, ...}) in any order and keeps, per window
and group, the count, sum, minimum and maximum.

Event time, not arrival time, decides the window: [start, start + window_s),
start = floor(ts / window_s) * window_s. The watermark is the largest timestamp
seen minus `lateness_s`; a window is closed once it ends at or before the
watermark, and an event for a closed window is counted as late and dropped, so
a closed window's result never changes. Aggregates survive restarts.

## Class `STREAM_PROCESSORAgent`

- `__init__(name)`
- `health_check()`
- `define(stream, window_s, value_field, key_field, lateness_s)`
- `ingest(stream, events)`
- `results(stream, closed_only)` — Window aggregates in time order; by default only closed windows, whose values are final.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_data_knowledge_stubs.py`, `velaris/tests/test_kan93_rest.py`, `velaris/tests/test_layer9_compute.py`
