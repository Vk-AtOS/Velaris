# CAUSALITY_RESOLVER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CAUSALITY_RESOLVER/main.py` (58 lines)

## Purpose

Causality resolver: merges observed cause-to-effect paths into one graph and ranks root causes.

resolve() takes paths such as ["supplier late", "stock-out", "missed delivery"]
(each a chain from cause to effect, e.g. from incident reviews). It counts how
often each link was reported, refuses a set of paths that contradicts itself
(A causes B in one, B causes A in another), and for an effect ranks the root
causes by the share of that effect's paths they start. It organises what was
reported; it does not test whether a link is truly causal.

## Class `CausalityResolver`

- `__init__(name)`
- `health_check()`
- `resolve(paths, effect)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.graph`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_aiie.py`, `velaris/tests/test_layer6_quantum.py`
