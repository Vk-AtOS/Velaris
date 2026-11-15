# NEURAL_POLICY_MESH

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/NEURAL_POLICY_MESH/main.py` (99 lines)

## Purpose

NEURAL_POLICY_MESH: every registered policy must agree before an intent goes ahead.

Not a neural network. It is a persistent register of named policies (each a
rule set with an owner) and a deny-overrides combination: enforce(intent)
evaluates the intent against every policy through EOF_POLICY, and the intent
is allowed only if no policy is violated and every policy could be evaluated.
With no policies registered nothing is allowed (fail closed).

Changing the register needs an authenticated caller (velaris.core.access): a governance
admin may add, replace or remove any policy; a policy's recorded owner may replace or
remove that one. The owner is the caller (an admin may name another owner). Every change
is traced. Policies passed to enforce(policies=...) are checked in addition to the
registered ones; they can only add restrictions, never replace the register.

## Class `NeuralPolicyMesh`

- `__init__(name)`
- `health_check()`
- `add_policy(name, policy_rules, owner)` — Register or replace a policy. Every rule must be well formed or a known built-in name.
- `remove_policy(name)`
- `list_policies()`
- `enforce(intent, policies)` — Check `intent` against every registered policy, plus any extra `policies` given (they only add).

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.EOF_POLICY.main`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/NEURAL_POLICY_MESH/policies.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_neuralgov.py`, `velaris/tests/test_aicore_b_prime_vcas.py`, `velaris/tests/test_layer5_neuralgov.py`
