# ACF_CONTEXT

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/ACF_CONTEXT/main.py` (60 lines)

## Purpose

ACF context: wraps a raw input in a screened envelope before anything acts on it.

contextualize(x) accepts text or an object and returns a signal with its kind,
a fingerprint (for de-duplication), the guard risk level, and text with
personal identifiers and secrets masked. Caller-supplied context (source,
actor, tenant, ...) is attached as given. Text that the guard blocks as an
injection attempt is not contextualised: the result says "blocked".

## Class `ACFContextAgent`

- `health_check()`
- `contextualize(x, context, now)`

## Depends on

- `velaris.agentkit.results`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ACF_CORE`, `ACF_ROUTER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_a_acf.py`, `velaris/tests/test_layer16_acf.py`
