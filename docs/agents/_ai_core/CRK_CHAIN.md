# CRK_CHAIN

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CRK_CHAIN/main.py` (79 lines)

## Purpose

CRK chain: puts the steps of an argument in dependency order and seals them.

A step is {"id", "claim", "kind": premise|inference|conclusion, "depends_on",
"evidence"}. build() rejects duplicate ids, unknown or circular dependencies,
orders the steps so every step follows what it depends on, and gives each a
digest that covers the step and everything before it. verify() recomputes the
digests, so a step edited, dropped or reordered afterwards is detected.
It checks structure only; CRK_VALIDATOR checks whether the steps are justified.

## Class `CRK_CHAINAgent`

- `__init__(name)`
- `health_check()`
- `build(steps)`
- `verify(chain)` — True only if every digest still matches the step it seals.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.graph`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CRK`, `CRK_REASONER`, `CRK_VALIDATOR`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_crk.py`, `velaris/tests/test_layer12_crk.py`
