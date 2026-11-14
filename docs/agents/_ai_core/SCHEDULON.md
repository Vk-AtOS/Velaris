# SCHEDULON

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/SCHEDULON/main.py` (51 lines)

## Purpose

_No module docstring yet._

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
- **tests:** `velaris/tests/test_schedulon.py`
