# HYPERSTATE_SYNTHESIZER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/HYPERSTATE_SYNTHESIZER/main.py` (50 lines)

## Purpose

HYPERSTATE_SYNTHESIZER: merges several partial state snapshots into one, reporting conflicts.

There is no "hyperstate": this is a deep merge. merge() takes a list of
nested dicts (or {"states": [...]} / {"resolved": [...]}), applies them in
order so that a later snapshot wins, merges nested objects key by key, and
lists every place where two snapshots held different values for the same
path, with the value kept. Lists are replaced, not concatenated.

## Class `HyperstateSynthesizer`

- `__init__(name)`
- `health_check()`
- `merge(resolved)` — Returns the merged state under "hyperstate", plus the conflicts found.

## Depends on

- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_neuralgov.py`, `velaris/tests/test_layer6_quantum.py`
