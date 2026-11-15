# HARD_LOCKDOWN_MODE

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/HARD_LOCKDOWN_MODE/main.py` (77 lines)

## Purpose

Hard lockdown mode: a persisted switch that denies every action except a small whitelist.
HardLockdownMode.enable() turns the lockdown on and disable() turns it off; both return True on
success and False when check_caller refuses (disabling needs a security admin, enabling only an
authenticated caller). is_enabled() and the enabled property read the stored flag. attempt(action)
returns True when the lockdown is off or the action is in the whitelist (heartbeat, core_status);
otherwise it returns False and records "BLOCKED: <action>". get_logs() returns a copy of those records.
State: the enabled flag is in JsonState, <VELARIS_DATA>/agents/HARD_LOCKDOWN_MODE/state.json, so a
restart does not lift a lockdown; the blocked log and counter are in memory only.
Failure: an unauthorised caller gets False (and the refusal is traced by check_caller); it does not raise.

## Class `HardLockdownMode`

Velaris Hard Lockdown Mode
- Full operational freeze for all agents except core security processes
- Every action is denied except explicit whitelist
- Overrides Soft Lockdown

- `__init__()`
- `enabled()`
- `enable()`
- `disable()`
- `is_enabled()`
- `attempt(action)` — Returns True only if:
- `get_logs()`

## Depends on

- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan104_unauthenticated_writes.py`
