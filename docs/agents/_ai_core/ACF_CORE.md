# ACF_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ACF_CORE/main.py` (45 lines)

## Purpose

ACF core: the intake pipeline that chains the other three ACF agents.

process(raw) runs ACF_CONTEXT (screen and envelope), then, when other sources
describe the same record, ACF_FUSION against each in turn, then ACF_ROUTER.
It stops at the first stage that refuses, and says which. A record whose
sources conflict is still routed, with the conflicts attached and
`signal.conflicted` set so a routing rule can send it to review.

## Class `ACFCoreAgent`

- `__init__(rules, default_destination)`
- `health_check()`
- `process(raw, sources, context, now)` — sources: optional [{"source", "data", "ts"?}] to merge into a record signal.

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.ACF_CONTEXT.main`
- `velaris.agents.ACF_FUSION.main`
- `velaris.agents.ACF_ROUTER.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_acf.py`, `velaris/tests/test_layer16_acf.py`
