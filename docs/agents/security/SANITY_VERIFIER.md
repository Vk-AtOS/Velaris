# SANITY_VERIFIER

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SANITY_VERIFIER/main.py` (172 lines)

## Purpose

SANITY_VERIFIER: last check on an agent's output, and a check of the runtime configuration.

verify(output) inspects a result before it is released and reports findings with
a severity. final_safe_output is True only when nothing is "high" or "critical":

  critical   not an object; text that the injection guard blocks
  high       any object inside the output (the output itself included) whose
             "status" is not "ok" - an upstream stage that reported no_schema,
             no_constraints, an error or anything else was not checked, so the
             result is not released. A payload that legitimately carries its own
             non-ok "status" field must be verified on its own, not inside a stage result.
  high       not JSON (or holds NaN/Infinity); larger than MAX_BYTES; nested deeper
             than MAX_DEPTH (an output over MAX_BYTES is rejected without a content
             scan; anything within it is scanned in full); a credential in the text (API key, private key, JWT,
             AWS key); instruction-like text scored "high" by the guard; a field
             missing from, or of the wrong type for, the caller's schema
  medium     personal identifiers in the text (email, phone, PAN, Aadhaar, card ...)
  low        faintly instruction-like text

Text screening is velaris.intel.guard's (heuristic: it can miss novel phrasing).
This verifier judges form and content hygiene; it cannot tell whether an answer is true.

verify_config(env) checks the settings Velaris reads from the environment
(VELARIS_DATA, VELARIS_MODEL, VELARIS_LLM_TIMEOUT, OLLAMA_URL and provider
credentials) for values that would break or weaken a run.

## Class `SanityVerifier`

- `__init__(name)`
- `health_check()`
- `verify(constrained, schema)` — Findings for one output. `schema` is {field: one of SCHEMA_TYPES} of required top-level fields.
- `verify_config(env)` — Findings about the environment settings Velaris reads. `env` defaults to this process's environment.

## Depends on

- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `NIRVANA`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_security_stubs.py`, `velaris/tests/test_layer5_neuralgov.py`
