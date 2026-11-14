# ACTION_MODELING_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ACTION_MODELING_CORE/main.py` (70 lines)

## Purpose

Action modelling core: orders the actions needed for an intent by their preconditions.

An intent is {"intent": name, "actions": [{"name", "needs": [facts], "gives":
[facts]}], "state": [facts already true]}. model() places an action only once
everything it needs is true, records which earlier step provides each need, and
reports actions that can never run with the facts they are missing. Actions may
also come from a playbook registered for the intent name. With no actions and
no playbook the plan is empty and the status says so; steps are never invented.

## Class `ActionModelingCore`

- `__init__(name, playbooks)`
- `health_check()`
- `model(intent)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `AIIE_KERNEL`, `DECISION_GRAPH_ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_AI_IE_layer.py`, `velaris/tests/test_aicore_a_aiie.py`
