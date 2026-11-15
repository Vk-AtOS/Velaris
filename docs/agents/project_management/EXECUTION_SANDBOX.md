# EXECUTION_SANDBOX

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/EXECUTION_SANDBOX/main.py` (150 lines)

## Purpose

Execution sandbox: evaluates a tiny arithmetic language (not Python) and logs every run.

safe_exec(code) parses the text and interprets it node by node; nothing is handed to exec or eval. Allowed: `name =
expression` and bare expressions over numbers, lists and tuples of numbers, names assigned earlier in the same call,
+ - * / // %, comparisons, and/or/not, `a if c else b`, and abs, min, max, sum and range. Everything else (imports,
attributes, strings, loops, comprehensions, lambdas, any other call) is refused. The result is the variable "_" if it
was assigned, otherwise the value of the last statement. It returns {"code", "status": "OK" or "ERROR", "result",
"error"}; a refusal, a syntax error or an arithmetic error comes back as "<Type>: message" and is never raised. Work is
bounded without a timer: 2000 characters, 300 syntax nodes, lists and range up to 10,000 items, integers up to 1024
bits. Variables do not persist between calls. get_last_result(), get_last_error() and get_log() (a copy) read back.
State: in memory only (last result, last error and the newest 500 log entries), per instance, lost on exit. No caller
check is made.

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
- **tests:** `velaris/tests/test_agents_coverage_a.py`, `velaris/tests/test_engine.py`, `velaris/tests/test_kan94_pm_agents.py`
