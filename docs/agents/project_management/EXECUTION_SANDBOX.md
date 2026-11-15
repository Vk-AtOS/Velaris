# EXECUTION_SANDBOX

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/EXECUTION_SANDBOX/main.py` (145 lines)

## Purpose

Execution sandbox: runs a code string with a restricted set of globals and logs every run.

safe_exec(code) parses and exec()s the code with only abs, min, max, sum and range available and an empty __builtins__;
the value of a variable named "_" afterwards is the result. It returns {"code", "status": "OK" or "ERROR", "result",
"error"}; a syntax error or any exception is caught and returned as a traceback string rather than raised. get_last_result(),
get_last_error() and get_log() read back. This restricts names only and is not a hardened security boundary: it has no
time or memory limit and must not be given untrusted code. State: in memory only, lost on exit.

## Class `Refused`

The code uses something outside the tiny arithmetic language.


## Class `ExecutionSandbox`

Velaris Execution Sandbox: a tiny ARITHMETIC language, not Python.
- Statements: `name = expression` and bare expressions; `_` holds the result
- Expressions: numbers, lists/tuples of numbers, names assigned earlier, + - * / // %, comparisons,
  and/or/not, `a if c else b`, and abs/min/max/sum/range
- Everything else (attributes, imports, strings, loops, comprehensions, lambdas, calls to anything else)
  is refused before anything runs. The code is interpreted node by node, never handed to exec, so there is
  no object graph to climb out through; size, integer width and list length are capped, and every call
  starts with empty variables (nothing persists between calls).
- ponytail: need loops or real programs? Run them in the process sandbox (OFFLINE_SANDBOX), not here.

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
- **tests:** `velaris/tests/test_agents_coverage_a.py`, `velaris/tests/test_kan94_pm_agents.py`
