# ACF_ROUTER

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/ACF_ROUTER/main.py` (94 lines)

## Purpose

ACF router: sends a signal to a destination by declared rules.

A rule is {"id", "if": [conditions], "to": destination, "priority"?}. The
highest-priority rule whose conditions all hold wins (id breaks ties). A signal
no rule matches goes to the default destination ("triage" unless configured
otherwise; None means such signals are refused). A signal the guard blocks, or
an ACF_CONTEXT result that was blocked, is quarantined and never routed.
Conditions read the signal's fields, e.g. "kind", "risk", "content.amount",
"context.source".

## Class `ACFRouterAgent`

- `__init__(rules, default_destination)`
- `health_check()`
- `set_rules(rules)` — Replace the rule set. A malformed rule rejects the whole set and leaves the old one in place.
- `route(signal)` — Accepts raw text, a signal object, or an ACF_CONTEXT.contextualize() result.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.conditions`
- `velaris.agentkit.results`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ACF_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_acf.py`, `velaris/tests/test_kan106_intake_guards.py`, `velaris/tests/test_layer16_acf.py`
