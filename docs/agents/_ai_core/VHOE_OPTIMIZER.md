# VHOE_OPTIMIZER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/VHOE_OPTIMIZER/main.py` (54 lines)

## Purpose

VHOE_OPTIMIZER: assigns a whole queue of work to a pool of workers.

Items are taken most important first (priority 1 is highest, then the earliest
"due", then id) and each is placed with VHOE_ROUTER against the loads built up
so far, so the important work gets capacity before the rest. The result lists
every assignment, what could not be assigned and why, and each worker's
utilisation afterwards.
ponytail: greedy, one pass. It respects priority and capacity but does not
search for the best overall packing; use an assignment solver if leftover
capacity is being wasted.

## Class `VHOE_OPTIMIZERAgent`

- `__init__()`
- `health_check()`
- `optimize(items, workers)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agents.VHOE_ROUTER.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `VHOE_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_vhoe.py`, `velaris/tests/test_layer21_vhoe.py`
