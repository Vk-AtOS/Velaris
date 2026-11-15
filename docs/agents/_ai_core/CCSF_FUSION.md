# CCSF_FUSION

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CCSF_FUSION/main.py` (26 lines)

## Purpose

CCSF fusion: merges snapshots of one entity reported by any number of systems.

fuse(sources) takes [{"source", "data", "ts"?}, ...] and returns the fields all
reporting systems agree on (with which systems reported each) and the fields
they disagree on, with every system's value and timestamp. It does not pick a
winner; that is CCSF_RESOLVER's job.

## Class `CCSF_FUSIONAgent`

- `health_check()`
- `fuse(sources)`

## Depends on

- `velaris.agentkit.aicore_a_fusion`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CCSF_CORE`, `CCSF_RESOLVER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_a_ccsf.py`, `velaris/tests/test_layer22_ccsf.py`
