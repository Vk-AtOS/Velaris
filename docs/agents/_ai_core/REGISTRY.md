# REGISTRY

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/REGISTRY/main.py` (118 lines)

## Purpose

Agent registry: discovers agents from their manifest.json files and loads or creates them by name.

At construction it scans each department folder (or the single base_path folder) one level down for
<AGENT>/manifest.json and indexes it by the manifest "name"; a manifest that is not valid JSON or has no "name" raises.
list_agents() returns the sorted names. get_agent_class(name) imports velaris.agents.<name>.<module> from the manifest
"entrypoint" ("main.py:ClassName") and returns the class; an unknown name or a missing or malformed entrypoint raises
ValueError. create(name, config) instantiates it, passing config only to a constructor whose first parameter is named "config";
any other constructor is called with its own defaults, and one with required arguments raises ValueError.
health_all() builds every agent and calls health_check(); an agent without one is reported as {"status":
"no_health_check"}, and a failure becomes {"status": "error", "error": ...} for that agent.
State: in-memory index only, rebuilt on every construction; nothing is written to disk.

## Class `AgentRegistry`

Discovers all agent modules under departments/<department>/*
Loads their entrypoints from manifest.json
Provides dynamic agent class loading.

- `__init__(base_path)`
- `health_check()`
- `list_agents()`
- `get_agent_class(agent_name)`
- `create(agent_name, config)` — Build the agent. `config` is passed only to a constructor whose first parameter is named `config`;
- `health_all()`

## Depends on

- `velaris.agents`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CONVERGENCE_BRIDGE`, `ENGINE`, `PRIME`
- **platform modules:** none found
- **tests:** `velaris/tests/test_alias_layers.py`, `velaris/tests/test_kan87_aicore_guards.py`, `velaris/tests/test_kan95_core.py`, `velaris/tests/test_registry.py`, `velaris/tests/test_system_integration.py`
