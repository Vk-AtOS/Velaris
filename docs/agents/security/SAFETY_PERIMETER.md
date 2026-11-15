# SAFETY_PERIMETER

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/SAFETY_PERIMETER/main.py` (49 lines)

## Purpose

Safety perimeter: a jurisdiction allow-list and a call-name deny-list, both failing closed.

check_jurisdiction(code) is True only for an exact string in allowed_jurisdictions (IN, SG, EU; case-sensitive).
check_syscall(call_name) is False for anything that is not a non-empty string, for eval, exec, compile, open,
__import__, input and breakpoint, for names starting with os., subprocess., sys., socket., ctypes. or shutil. (compared
without regard to case, after trimming), and for the entries of blocked_syscalls. can_execute(jurisdiction_code,
syscall_name) needs both checks to pass. execution_gate_enabled is a read-only property that is always True: the gate
has no off switch (assigning to it raises AttributeError).
State: the two lists are per-instance attributes in memory, which code holding the instance can edit; nothing is
persisted. A name deny-list is a guard rail, not a sandbox: it judges the name it is given and runs nothing.

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
