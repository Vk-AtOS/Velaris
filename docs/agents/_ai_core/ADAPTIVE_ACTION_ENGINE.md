# ADAPTIVE_ACTION_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ADAPTIVE_ACTION_ENGINE/main.py` (59 lines)

## Purpose

Adaptive action engine: tries the action that has worked best for this kind of situation.

Given a situation name and candidate actions, act() ranks the candidates by
their recorded success in that situation (AUTO_LEARN_CORE), runs the first one
AAE_POLICY lets through via AAE_RUNTIME, and records whether it succeeded, so
the ranking changes as evidence accumulates. "Adaptive" here means exactly
that: success counts per situation, no trained model. It keeps no state of its
own; outcomes live in AUTO_LEARN_CORE and the action journal in AAE_RUNTIME.

## Class `ADAPTIVE_ACTION_ENGINEAgent`

- `__init__(runtime)`
- `health_check()`
- `choose(situation, candidates)` — Rank candidate actions ({"id", "type", "params"?}) for a situation without running anything.
- `act(situation, candidates, approved_by)` — Run the best-ranked candidate policy allows; record its outcome. Others are reported as passed over.
- `feedback(situation, action_type, success)` — Record an outcome learned later (e.g. the reminder was sent, but did the invoice get paid?).

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agents.AAE_RUNTIME.main`
- `velaris.agents.AUTO_LEARN_CORE.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_aae.py`, `velaris/tests/test_layer25_aae.py`
