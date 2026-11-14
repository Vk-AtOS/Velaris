# CRK_CONTEXT

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/CRK_CONTEXT/main.py` (59 lines)

## Purpose

CRK context: turns raw facts into a screened fact set that rules can safely run on.

Each fact is {"key", "value", "source"}. Text values are scanned for
instruction-like content (velaris.intel.guard): blocked text is dropped, and
personal identifiers and secrets are masked. Two different values for one key
are reported as a conflict (the first is kept), and facts beyond the size
budget are listed as truncated instead of silently lost.

## Class `CRK_CONTEXTAgent`

- `__init__(name, budget_chars)`
- `health_check()`
- `build(facts)` — Returns facts ({key: {"value", "source", "risk"}}), values ({key: value}) and what was left out.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CRK`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_crk.py`, `velaris/tests/test_layer12_crk.py`
