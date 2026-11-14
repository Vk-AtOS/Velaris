# VHOE_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/VHOE_CORE/main.py` (42 lines)

## Purpose

VHOE_CORE: one planning pass over the work queue.

plan(items, workers, history) assigns the queue with VHOE_OPTIMIZER and, when
past completion records are given, adds VHOE_ANALYTICS' picture of how work
has been going. It then flags what a manager should look at: unassigned work,
workers above 90% utilisation, and a late rate above 20%.

## Class `VHOE_COREAgent`

- `__init__()`
- `health_check()`
- `plan(items, workers, history)`

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.VHOE_ANALYTICS.main`
- `velaris.agents.VHOE_OPTIMIZER.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_vhoe.py`, `velaris/tests/test_layer21_vhoe.py`
