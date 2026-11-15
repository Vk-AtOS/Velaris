# NEURAL_MESH

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/NEURAL_MESH/main.py` (51 lines)

## Purpose

_No module docstring yet._

## Class `NeuralMesh`

Simple routing mesh for agent messages.
Stores conversation context into MemoryFabric and routes messages using scores.

- `__init__(config)`
- `health_check()`
- `route(from_agent, to_agent, payload, context_key)` — Queue `payload` in `to_agent`'s inbox. ok is True only when it was queued; "delivered" is always False
- `broadcast(agents, payload, context_key)`
- `receive(agent)` — Messages queued for `agent`, oldest first; they are removed from the inbox.

## Depends on

- `velaris.agents.MEMORY_FABRIC.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_infra_agents.py`, `velaris/tests/test_kan106_aicore.py`
