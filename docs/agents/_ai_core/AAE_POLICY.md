# AAE_POLICY

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/AAE_POLICY/main.py` (106 lines)

## Purpose

AAE policy: decides whether a proposed action may run.

Rules are {"id", "effect": allow|deny|require_approval, "if": [conditions]}.
For an action, a matching deny wins, then a matching require_approval, then a
matching allow. An action no rule matches is denied, and so is everything when
no rules are loaded or the stored rules are unreadable. Conditions read the
action's fields ("type", "params.amount", "actor", ...) and are three-valued
(velaris.agentkit.conditions): a deny or require_approval rule none of whose
conditions is false, but one of which cannot be evaluated (field missing, text
where a number is compared, a list where a scalar is), denies the action outright;
an allow rule needs every condition to hold.
State (the rule set): <VELARIS_DATA>/agents/AAE_POLICY/state.json.

## Class `AAE_POLICYAgent`

- `__init__(rules)` — `rules` given here are used as they are and not stored; otherwise the stored set is used.
- `health_check()`
- `set_rules(rules)` — Validate and store a rule set. A malformed set is rejected whole; the old one stays.
- `rules()`
- `decide(action)` — Returns decision allow | needs_approval | deny, with the rule that decided it.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.conditions`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/AAE_POLICY/state.json`

## Called by

- **other agents:** `AAE_RUNTIME`, `ADAPTIVE_ACTION_ENGINE`, `REGISTRY`
- **platform modules:** `velaris/orchestration/autonomy.py`
- **tests:** `velaris/tests/test_aicore_a_aae.py`, `velaris/tests/test_autonomy.py`, `velaris/tests/test_kan104_operator_clear.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_kan95_core.py`, `velaris/tests/test_layer25_aae.py`, `velaris/tests/test_security_review_round2.py`
