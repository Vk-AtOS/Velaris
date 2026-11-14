# MPC_FUSION

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/MPC_FUSION/main.py` (63 lines)

## Purpose

MPC_FUSION: merges records about the same thing from several sources into one, field by field.

Each source is {"source": name, "record": {...}, "trust": 0..1 (default 0.5),
"ts": when it was read (default 0)}. For every field: if all sources that have
it agree, that value is used. If they disagree the winner is the value from
the most trusted source, then the most recent, then the value most sources
hold, then the first source by name; the disagreement is listed in
"conflicts" with every candidate, so a person can overrule it. "provenance"
says which source each fused value came from.

## Class `MPC_FUSIONAgent`

- `health_check()`
- `fuse(sources)` — Returns record, provenance, conflicts and agreement (share of fields with no conflict).

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MPC_CORE`, `MPC_PREPROC`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mpc.py`, `velaris/tests/test_layer24_mpc.py`
