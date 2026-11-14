# VHOE_ROUTER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/VHOE_ROUTER/main.py` (66 lines)

## Purpose

VHOE_ROUTER: assigns one piece of work to the person or agent best placed to take it.

VHOE is read here as "human-and-agent operations": a pool of workers (people
or agents) with skills and limited capacity, and a queue of work items.

route(item, workers) picks, among the workers who have the item's skill and
enough free capacity for its effort, the one with the lowest utilisation
(load / capacity); ties go to the worker id that sorts first. When nobody
qualifies it says whether the skill or the capacity was missing.

item:   {"id", "skill", "effort": hours (default 1)}
worker: {"id", "skills": [...], "capacity": hours, "load": hours (default 0)}

## Class `VHOE_ROUTERAgent`

- `health_check()`
- `route(item, workers)` — Returns the chosen worker id, or status "unassigned" with the reason.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `VHOE_OPTIMIZER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_vhoe.py`, `velaris/tests/test_layer21_vhoe.py`
