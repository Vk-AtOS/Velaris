# EXECUTION_SANDBOX

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/EXECUTION_SANDBOX/main.py` (62 lines)

## Purpose

Execution sandbox: runs a code string with a restricted set of globals and logs every run.

safe_exec(code) parses and exec()s the code with only abs, min, max, sum and range available and an empty __builtins__;
the value of a variable named "_" afterwards is the result. It returns {"code", "status": "OK" or "ERROR", "result",
"error"}; a syntax error or any exception is caught and returned as a traceback string rather than raised. get_last_result(),
get_last_error() and get_log() read back. This restricts names only and is not a hardened security boundary: it has no
time or memory limit and must not be given untrusted code. State: in memory only, lost on exit.

## Class `ExecutionSandbox`

Velaris Execution Sandbox
- Safe code execution environment
- Blocks dangerous builtins
- Tracks executed operations

- `__init__()`
- `safe_exec(code)`
- `get_last_result()`
- `get_last_error()`
- `get_log()`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_a.py`
