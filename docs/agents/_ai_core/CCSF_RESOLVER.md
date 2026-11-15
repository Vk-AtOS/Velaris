# CCSF_RESOLVER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CCSF_RESOLVER/main.py` (84 lines)

## Purpose

CCSF resolver: settles conflicting field values by a declared strategy per field.

Strategies ({field: strategy}, with a default for unlisted fields):
  "latest"                          value with the newest timestamp
  {"priority": [source, ...]}       value from the first listed source that reported
  "majority"                        value reported by more than half the sources
  "max" / "min"                     largest / smallest numeric value
  "manual"                          leave it for a person (the default)
A strategy that cannot decide (missing or equal timestamps, no majority,
non-numeric values, no listed source) leaves the field unresolved with the reason.

## Class `CCSF_RESOLVERAgent`

- `health_check()`
- `resolve(conflicts, strategies, default)` — conflicts: the list from CCSF_FUSION / ACF_FUSION. Returns resolved and unresolved fields.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ACF_FUSION`, `CCSF_CORE`, `CCSF_FUSION`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_ccsf.py`, `velaris/tests/test_layer22_ccsf.py`
