# CRK_VALIDATOR

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CRK_VALIDATOR/main.py` (97 lines)

## Purpose

CRK validator: checks every step of an argument against fixed rules and names the first that fails.

Rules, applied in chain order:
  premise     must cite evidence, and every cited key must be a known fact
  inference   must depend on at least one earlier step; if it carries a numeric
              "check" ({"left", "op", "right"}, operands are numbers or
              {"fact": key}), the check must hold
  conclusion  exactly one, last, depending on at least one step
A step the conclusion does not rest on is a warning, not a failure.
Anything that cannot be checked counts as failed. The validator does not judge
whether a claim's wording is true; it checks that the declared support exists.

## Class `CRK_VALIDATORAgent`

- `__init__(name)`
- `health_check()`
- `validate(chain, facts, require_conclusion)` — `chain` is a CRK_CHAIN.build() result or a raw list of steps. Returns valid, failed_step, reason.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.conditions`
- `velaris.agentkit.results`
- `velaris.agents.CRK_CHAIN.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CRK`, `CRK_CHAIN`, `CRK_REASONER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_crk.py`, `velaris/tests/test_layer12_crk.py`
