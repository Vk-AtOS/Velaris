# CRK_CHAIN

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CRK_CHAIN/main.py` (85 lines)

## Purpose

CRK chain: puts the steps of an argument in dependency order and seals them.

A step is {"id", "claim", "kind": premise|inference|conclusion, "depends_on",
"evidence"}. build() rejects duplicate ids, unknown or circular dependencies,
orders the steps so every step follows what it depends on, and gives each a
digest that covers the step, its position (seq) and everything before it. verify() recomputes the
digests and checks seq runs 1..n, so a step edited, dropped, reordered or renumbered afterwards is detected. A step
keeps only the sealed fields (id, claim, kind, depends_on, evidence, check): anything else a caller adds is dropped, so
nothing unsealed travels with a sealed chain. `check` must be an object ({"left", "op", "right"}, see CRK_VALIDATOR) of at most 2000 characters as JSON when given.
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
- **tests:** `velaris/tests/test_aicore_a_crk.py`, `velaris/tests/test_layer12_crk.py`, `velaris/tests/test_r3_csm_crk_eac.py`
