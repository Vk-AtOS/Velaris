# AGENT_LIFECYCLE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/AGENT_LIFECYCLE/main.py` (38 lines)

## Purpose

Agent lifecycle: message-style front for AGENT_LIFECYCLE_MANAGER.

run({"action": "set" | "get" | "history" | "list", "agent", "state", "reason"})
maps one request onto the manager, which holds the state machine and the state
file. This class adds no rules of its own.

## Class `AgentLifecycleAgent`

- `__init__(config)`
- `health_check()`
- `run(payload)`

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.AGENT_LIFECYCLE_MANAGER.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `AGENT_LIFECYCLE_MANAGER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_ops.py`
