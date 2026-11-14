# ACF_FUSION

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ACF_FUSION/main.py` (32 lines)

## Purpose

ACF fusion: merges two records about the same thing and reports where they disagree.

fuse(a, b) takes two objects (plain data, or {"source", "data", "ts"}) and
returns the fields they agree on or that only one has, which source each came
from, and the conflicting fields with both values. Conflicts are left out of
the merged record; CCSF_RESOLVER can settle them by a declared rule.

## Class `ACFFusionAgent`

- `health_check()`
- `fuse(a, b)` — `fusion` is True only when both inputs were usable; `clean` is True when nothing conflicted.

## Depends on

- `velaris.agentkit.aicore_a_fusion`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ACF_CORE`, `CCSF_RESOLVER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_acf.py`, `velaris/tests/test_layer16_acf.py`
