# HYPER_REASONER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/HYPER_REASONER/main.py` (80 lines)

## Purpose

HYPER_REASONER: structural validation of a decision graph before anything is planned from it.

It does not reason about content. reason(graph) accepts
  {"nodes": ["a", {"id": "b"}, ...], "edges": [["a", "b"], {"from": "b", "to": "c"}], "start": "a"}
  or {"steps": [...]} (a plain sequence), optionally wrapped as {"graph": ...}
and checks: there is at least one node, ids are unique, every edge joins known
nodes, there is no cycle, and every node can be reached from the start (the
given start, or the nodes nothing points to). "validated" is True only when
no issue is found; the issues and a valid execution order are returned, and
for a valid graph "steps" lists each node with what it depends on (the input
RECURSIVE_GOAL_PLANNER takes).

## Class `HyperReasoner`

- `__init__(name)`
- `health_check()`
- `reason(graph)`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `AIIE_KERNEL`, `RECURSIVE_GOAL_PLANNER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_AI_IE_layer.py`, `velaris/tests/test_aicore_b_aiie.py`
