# CRK_INTENT

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/CRK_INTENT/main.py` (94 lines)

## Purpose

CRK intent: names what a short request is asking for, from a fixed list of intents.

Keyword rules decide first. Only when no rule (or more than one) matches is a
language model asked, through velaris.intel.llm; its answer is accepted only if
it is one of the allowed intent names. With no model available the result is
"not_configured" with the tied candidates, never a guess. Requests containing
instruction-like text are refused before any of that.
A model is used when one is passed in or VELARIS_MODEL is set.

## Class `CRK_INTENTAgent`

- `__init__(name, intents, llm)`
- `health_check()`
- `classify(text)` — Returns {"status", "intent", "method", ...}. `intent` is None unless status is ok.

## Depends on

- `velaris.agentkit.results`
- `velaris.intel`
- `velaris.intel.llm`

## State and configuration

- keeps no files of its own
- env var: `VELARIS_MODEL`

## Called by

- **other agents:** `CRK`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_crk.py`, `velaris/tests/test_kan106_aicore.py`, `velaris/tests/test_layer12_crk.py`
