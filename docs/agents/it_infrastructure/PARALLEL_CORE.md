# PARALLEL_CORE

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/PARALLEL_CORE/main.py` (70 lines)

## Purpose

PARALLEL_CORE: run one function over many inputs on a bounded thread pool.

map() returns one record per input, in input order: {"ok": True, "value": ...}
or {"ok": False, "error": "..."} - one failing input never loses the others.
Threads suit I/O-bound work (model calls, files, HTTP); CPU-bound pure Python
gains nothing from them.

ponytail: a Python thread cannot be killed, so an input that outlives
`timeout_s` is reported as timed out while its thread runs on to completion in
the background. Use a subprocess (OFFLINE_SANDBOX) for work that must be stoppable.

## Class `PARALLEL_COREAgent`

- `__init__(name)`
- `health_check()`
- `default_workers()`
- `map(fn, items, workers, timeout_s)` — Apply fn to each item concurrently; `timeout_s` bounds the whole call.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs.py`, `velaris/tests/test_layer9_compute.py`
