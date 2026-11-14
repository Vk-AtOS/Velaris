# EOF_POLICY

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/EOF_POLICY/main.py` (72 lines)

## Purpose

EOF_POLICY: checks one record (a plan step, an action) against one declared policy.

EOF is read here as "execution orchestration framework": EOF_CORE orders a
plan, this agent says whether each step complies, EOF_GATEWAY hands the step
to its target.

A policy is {"name": ..., "rules": [...]}. Each rule is a rule object (see
velaris.agentkit.aicore_b_rules) or the name of a built-in rule below.
Deterministic; fails closed: an unknown rule name, a malformed rule, an empty
policy or a missing subject is never "compliant".

## Class `EOF_POLICYAgent`

- `health_check()`
- `evaluate(policy, subject)` — Is `subject` compliant with `policy`? Returns compliant, violations, errors, checked.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CORE_CONVERGENCE`, `EOF_CORE`, `NEURAL_POLICY_MESH`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_eof.py`, `velaris/tests/test_layer31_eof.py`
