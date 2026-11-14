# VHOE_ANALYTICS

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/VHOE_ANALYTICS/main.py` (54 lines)

## Purpose

VHOE_ANALYTICS: how the work actually went, from completed-work records.

analyse(records) takes records of {"id", "worker", "started", "finished",
"due" (optional)} with times as epoch seconds and reports: how many were
completed, cycle time (finished - started) mean / median / 90th percentile in
hours, how many finished after their due time, and the same per worker.
Records with missing or impossible times are skipped and counted, never guessed.

## Class `VHOE_ANALYTICSAgent`

- `health_check()`
- `analyse(records)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `VHOE_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_vhoe.py`, `velaris/tests/test_layer21_vhoe.py`
