# ASEL_ROUTER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ASEL_ROUTER/main.py` (58 lines)

## Purpose

ASEL router: decides which handler carries out each plan step.

A step names the `capability` it needs; a handler lists the capabilities it
has. Each step goes to the capable handler with the fewest steps so far (name
breaks ties), respecting an optional `max_steps` per handler. Steps nobody can
take are returned as unroutable; they are not given to a default handler.

## Class `ASEL_ROUTERAgent`

- `__init__(name)`
- `health_check()`
- `route(steps, handlers)` — steps: list (or a planner result) of {"id", "capability"}; handlers: [{"name", "capabilities", "max_steps"?}].

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ASEL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_a_asel.py`, `velaris/tests/test_layer13_asel.py`
