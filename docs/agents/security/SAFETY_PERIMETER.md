# SAFETY_PERIMETER

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/SAFETY_PERIMETER/main.py` (32 lines)

## Purpose

Safety perimeter: a static allow-list gate on jurisdiction and syscall name.
SafetyPerimeter.check_jurisdiction(code) is True for IN, SG or EU. check_syscall(call_name) is False
for os.system, subprocess.Popen, eval and exec. can_execute(jurisdiction_code, syscall_name) is True
only when both pass, or always True when execution_gate_enabled is False. It compares exact strings
only, so it is a simple policy check and not a sandbox: it cannot stop code that does not name itself.
State: fixed lists on the instance, nothing persisted, no caller check. Failure: unknown values
simply return False; it never raises, and the gate can be switched off by setting the attribute.

## Class `SafetyPerimeter`

- `__init__()`
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
- **tests:** `velaris/tests/test_agents_coverage_c.py`
