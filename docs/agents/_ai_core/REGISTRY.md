# REGISTRY

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/REGISTRY/main.py` (95 lines)

## Purpose

_No module docstring yet._

## Class `AgentRegistry`

Discovers all agent modules under departments/<department>/*
Loads their entrypoints from manifest.json
Provides dynamic agent class loading.

- `__init__(base_path)`
- `health_check()`
- `list_agents()`
- `get_agent_class(agent_name)`
- `create(agent_name, config)`
- `health_all()`

## Depends on

- `velaris.agents`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CONVERGENCE_BRIDGE`, `ENGINE`, `PRIME`
- **platform modules:** none found
- **tests:** `velaris/tests/test_registry.py`, `velaris/tests/test_system_integration.py`
