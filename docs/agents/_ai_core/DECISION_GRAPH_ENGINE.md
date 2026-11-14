# DECISION_GRAPH_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/DECISION_GRAPH_ENGINE/main.py` (53 lines)

## Purpose

Decision graph engine: turns a plan into a dependency graph and checks it can be followed.

graph() accepts {"steps": [{"id", "depends_on"}]} (as ACTION_MODELING_CORE and
ASEL_PLANNER produce) or {"plan": [names]} (taken as a strict sequence). It
returns nodes, edges, the levels of steps that can proceed together, roots and
leaves, and refuses plans with unknown or circular dependencies.

## Class `DecisionGraphEngine`

- `__init__(name)`
- `health_check()`
- `graph(plan)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.graph`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `AIIE_KERNEL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_AI_IE_layer.py`, `velaris/tests/test_aicore_a_aiie.py`, `velaris/tests/test_aicore_b_aiie.py`
