# AGENT_CONTAINMENT_MODES

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/AGENT_CONTAINMENT_MODES/main.py` (45 lines)

## Purpose

_No module docstring yet._

## Class `AgentContainmentModes`

Velaris Agent Containment Modes
- Supports SANDBOX, ISOLATION, and FULL_LOCK modes
- Controls operational constraints on agents
- Tracks status per agent

- `__init__()`
- `set_mode(agent, mode)`
- `get_mode(agent)`
- `set_metadata(agent, info)`
- `get_metadata(agent)`
- `allowed_actions(agent)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
