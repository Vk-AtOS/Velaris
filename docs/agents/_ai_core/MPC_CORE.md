# MPC_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/MPC_CORE/main.py` (38 lines)

## Purpose

MPC_CORE: clean every source's record (MPC_PREPROC), then merge them (MPC_FUSION).

Cleaning first is what makes the merge meaningful: "1,200" from one system and
1200.0 from another, or "Total Amount" and "total_amount", are the same value
and the same field once cleaned, so they no longer show up as conflicts.

## Class `MPC_COREAgent`

- `__init__()`
- `health_check()`
- `run(sources, redact)` — sources: [{"source", "record", "trust", "ts"}]. Returns the fusion result plus cleaning stats.

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.MPC_FUSION.main`
- `velaris.agents.MPC_PREPROC.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MPC_PREPROC`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_mpc.py`, `velaris/tests/test_layer24_mpc.py`
