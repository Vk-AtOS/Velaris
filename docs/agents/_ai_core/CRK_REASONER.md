# CRK_REASONER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CRK_REASONER/main.py` (102 lines)

## Purpose

CRK reasoner: forward-chaining rule inference over a set of facts.

A rule is {"id", "if": [conditions], "then": {field: value}}; a condition is
{"field", "op", "value"}. Rules fire in id order, repeatedly, until nothing new
can be derived. A rule that would overwrite an existing fact with a different
value is not applied and is reported as a conflict. Every derived fact is
recorded as a step in a CRK_CHAIN, and when a `goal` field is derived the chain
is checked by CRK_VALIDATOR. This is rule evaluation: it derives exactly what
the supplied rules entail and nothing else.

## Class `CRK_REASONERAgent`

- `__init__(name, max_rounds)`
- `health_check()`
- `reason(facts, rules, goal)` — Returns derived facts, the rules that fired, conflicts, the chain and (with a goal) its validation.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.conditions`
- `velaris.agentkit.results`
- `velaris.agents.CRK_CHAIN.main`
- `velaris.agents.CRK_VALIDATOR.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CRK`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_crk.py`, `velaris/tests/test_layer12_crk.py`
