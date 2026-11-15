# AGENT_CONTAINMENT_MODES

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/AGENT_CONTAINMENT_MODES/main.py` (65 lines)

## Purpose

Agent containment modes: records a containment level per agent and says which actions that level allows.

set_mode(agent, mode) accepts SANDBOX, ISOLATION or FULL_LOCK for a non-empty agent name; it returns False for an invalid
mode or name, or when the caller is not a security administrator (the attempt is traced). set_metadata(agent, info) has the
same caller rule. get_mode(agent) returns the mode or "UNSET"; get_metadata(agent) returns the stored dict or {}.
allowed_actions(agent) returns ["read", "compute"] for SANDBOX, ["compute"] for ISOLATION and [] for FULL_LOCK or UNSET.
It only reports the policy; it does not itself stop an agent from acting. State: in memory only (lost on exit, so modes
must be set again after a restart); reads need no caller.

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

- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan104_unauthenticated_writes.py`
