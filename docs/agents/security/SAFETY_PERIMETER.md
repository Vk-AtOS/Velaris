# SAFETY_PERIMETER

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/SAFETY_PERIMETER/main.py` (38 lines)

## Purpose

_No module docstring yet._

## Class `SafetyPerimeter`

Velaris Safety Perimeter
- Jurisdiction allow-list and a call deny-list, both fail closed (anything that is not a plain, known-good
  value is refused). The gate cannot be switched off from outside.
- ponytail: a name deny-list is a guard rail, not a sandbox; real isolation is the process sandbox.

- `__init__()`
- `execution_gate_enabled()`
- `check_jurisdiction(code)`
- `check_syscall(call_name)`
- `can_execute(jurisdiction_code, syscall_name)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan88_security_agents.py`
