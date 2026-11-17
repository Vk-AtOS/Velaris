# SOFT_LOCKDOWN_MODE

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SOFT_LOCKDOWN_MODE/main.py` (76 lines)

## Purpose

Soft lockdown mode: a persistent on/off switch that blocks a fixed list of high-risk actions while on.

enable() may be called by any authenticated caller; disable() needs a security administrator. Both are traced, and both
return False when the caller is refused. is_enabled() reads the flag. attempt(action) returns False and logs "Blocked:
<action>" when lockdown is on and the action is one of modify_core, install_external, change_security, access_sensitive;
otherwise True. get_logs() returns the blocked-attempt log. Rule-based: it does not enforce anything outside callers that
ask attempt() first. State: the enabled flag is in JsonState under <VELARIS_DATA>/agents/SOFT_LOCKDOWN_MODE/state.json so a
restart does not lift a lockdown; the blocked-attempt log is in memory only.

## Class `SoftLockdownMode`

Velaris Soft Lockdown Mode
- Restricts high-risk actions, but allows normal operations
- Tracks lockdown Enable/Disable state
- Logs attempted restricted actions

- `__init__()`
- `enabled()`
- `enable()`
- `disable()`
- `is_enabled()`
- `attempt(action)` — Returns True if action is allowed.
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
