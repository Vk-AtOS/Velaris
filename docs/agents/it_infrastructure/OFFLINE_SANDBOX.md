# OFFLINE_SANDBOX

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/OFFLINE_SANDBOX/main.py` (148 lines)

## Purpose

OFFLINE_SANDBOX: run a small allow-list of read-only commands, contained as a process.

THIS IS PROCESS ISOLATION, NOT A SECURITY SANDBOX. There is no namespace,
seccomp, chroot or resource limit: a command here runs as the current user. What
this agent does guarantee is narrower and exact:

  - only the commands in allowed() run, resolved to a binary in /usr/bin or /bin
  - no shell: arguments are passed as a list, so nothing is expanded or chained
  - an argument may not contain "/" or "..", start with "~" or hold a NUL, so a
    file operand can only name a file in the working directory
  - an argument starting with "-" must be one of that command's _FLAGS, exactly
    (no bundling, no long options, no "--"); a flag that takes a value is followed
    by a count. This shuts out option-driven escapes such as GNU
    `wc --files0-from=FILE` or `tail --follow=name`. The allowed flags were checked
    against GNU coreutils and the macOS (BSD) tools: none of them reads a file other
    than its operands, writes anything, or runs another program
  - the working directory is a fresh temporary directory holding only the files
    the caller passed in, and it is deleted afterwards
  - the environment is replaced (PATH, LANG, HOME, TMPDIR only): no secrets leak in
  - a timeout kills the process group this agent started; output is capped

Everything else is refused. safe() answers whether a command would be allowed
without running it.

## Class `OfflineSandbox`

- `__init__(name)`
- `health_check()`
- `allowed()`
- `safe(payload)` — Would this command be allowed? `payload` is an argv list or {"argv": [...]}. Runs nothing.
- `run(argv, timeout_s, files, stdin)` — Run an allow-listed command. `files` ({name: text}) are placed in its working directory.

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `EXECUTION_SANDBOX`, `OFFLINE_EXECUTION_ENGINE`, `PARALLEL_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer7_offline.py`
