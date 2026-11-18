# SELF_CORRECTION_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/SELF_CORRECTION_ENGINE/main.py` (112 lines)

## Purpose

SELF_CORRECTION_ENGINE: repairs a record against a declared schema and says what it changed.

Schema: {field: {"type": "number" | "integer" | "string" | "boolean", "required": bool,
"default": ..., "min": n, "max": n, "choices": [...], "max_length": n, "money": true}}.
A "money" field is never clamped: an amount outside min..max is reported as unfixable.

Repairs made (each one listed in "corrections"): numeric text to a number
("1,200.50"), yes/no text to a boolean, surrounding whitespace removed, a
number outside min..max clamped to the bound, a choice matched ignoring case,
an over-long string cut, a missing field filled from its default. What cannot
be repaired (a missing required field with no default, text that is not a
number, a value outside the choices) is listed in "unfixable" and the status
says so. Fields the schema does not mention are left alone.

## Class `SelfCorrectionEngine`

- `__init__(name)`
- `health_check()`
- `correct(adaptive, schema)` — Returns the corrected record, the corrections made and what could not be fixed.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `NIRVANA`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_neuralgov.py`, `velaris/tests/test_kan106_aicore.py`, `velaris/tests/test_kan95_core.py`, `velaris/tests/test_layer5_neuralgov.py`
