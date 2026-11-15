# CUSTOS

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/CUSTOS/main.py` (38 lines)

## Purpose

Custos: minimal in-memory role-based access check.

CustosAgent(config; "roles", "permissions"): health_check(); define_role(role, perms)
sets the role's permission set; assign_permission(role, permission) adds one (creating the
role if needed); check_access(role, action) is True if the action is in the role's set.
State: in memory only (self.roles), lost on restart. A "roles" config must map to sets,
since lists would break assign_permission.
Failure: an unknown role or action returns False (deny); it does not identify callers.

## Class `CustosAgent`

- `__init__(config)`
- `health_check()`
- `define_role(role, perms)`
- `assign_permission(role, permission)`
- `check_access(role, action)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `PRIME`
- **platform modules:** none found
- **tests:** `velaris/tests/test_custos.py`, `velaris/tests/test_engine.py`, `velaris/tests/test_kan88_security_agents.py`, `velaris/tests/test_system_integration.py`
