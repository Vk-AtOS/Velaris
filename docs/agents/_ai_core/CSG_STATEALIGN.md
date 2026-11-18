# CSG_STATEALIGN

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CSG_STATEALIGN/main.py` (60 lines)

## Purpose

CSG state align: compares the state something should have with the state it has, and produces the fix.

align(expected, actual) returns a patch: the fields to add, replace or remove
to make `actual` equal `expected` (nested objects are compared field by field,
addressed by dotted paths). apply() applies such a patch to a state and returns
the new state without modifying the input.
ponytail: dotted paths, so field names that themselves contain a dot are not
supported; switch to path lists if such keys ever appear.

## Class `CSG_STATEALIGNAgent`

- `health_check()`
- `align(expected, actual)`
- `apply(state, patch)`

## Depends on

- `velaris.agentkit.aicore_a_fusion`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `COHERENCE_SYNC_CORE`, `HYPERSYNC`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_csg.py`, `velaris/tests/test_kan106_aicore.py`, `velaris/tests/test_layer28_csg.py`
