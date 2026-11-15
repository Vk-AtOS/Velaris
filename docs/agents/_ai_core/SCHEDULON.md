# SCHEDULON

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/SCHEDULON/main.py` (65 lines)

## Purpose

Schedulon: greedy load distribution across workers and least-loaded worker lookup.

SchedulonAgent(config): health_check() returns agent, status and version (config
"version", default 0.1.0); distribute_load(tasks, workers) assigns each integer load in
order to the bucket with the smallest running total and returns the list of buckets;
next_available_slot(schedule) takes {worker: load} and returns the worker with the
smallest load.
State: keeps no state.
Failure: distribute_load returns [] when workers is not an int (or is a bool) or is below
1; next_available_slot returns None for an empty schedule; non-numeric loads raise TypeError.

## Class `SchedulonAgent`

- `__init__(config)`
- `health_check()`
- `distribute_load(tasks, workers)` — Distribute task loads (ints) across N workers as evenly as possible.
- `next_available_slot(schedule)` — Return worker ID (str) with smallest assigned load.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan106_aicore.py`, `velaris/tests/test_schedulon.py`
