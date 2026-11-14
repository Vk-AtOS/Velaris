# NEURAL_MESH

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/NEURAL_MESH/main.py` (37 lines)

## Purpose

_No module docstring yet._

## Class `NeuralMesh`

Simple routing mesh for agent messages.
Stores conversation context into MemoryFabric and routes messages using scores.

- `__init__(config)`
- `health_check()`
- `route(from_agent, to_agent, payload, context_key)`
- `broadcast(agents, payload, context_key)`

## Depends on

- `velaris.agents.MEMORY_FABRIC.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_infra_agents.py`
