# NEURAL_MESH

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/NEURAL_MESH/main.py` (57 lines)

## Purpose

Neural mesh: a message queue between agents, backed by MEMORY_FABRIC.

route(from_agent, to_agent, payload, context_key=None) appends the message to to_agent's
inbox and optionally stores it under a context key; it returns ok/queued True and delivered
False (nothing is pushed to the receiver). A missing to_agent or a non-dict payload returns
ok False with a reason. broadcast(agents, payload, context_key=None) routes to each agent
(returns {} if agents is not a list). receive(agent) returns the queued messages oldest
first and empties the inbox. No scoring or ranking is done despite the class note.
State: MemoryFabric namespaces neural_inbox, neural_context, neural_broadcast.

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
- **tests:** `velaris/tests/test_infra_agents.py`, `velaris/tests/test_kan106_aicore.py`, `velaris/tests/test_kan89_aicore.py`
