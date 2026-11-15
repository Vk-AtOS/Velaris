# CSM_POLICY

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CSM_POLICY/main.py` (72 lines)

## Purpose

CSM policy: builds a checkable policy from a short specification, and checks records against it.

generate_policy() takes {"name", "required": [fields], "limits": {field:
{"min"?, "max"?}}, "allowed": {field: [values]}} and returns explicit rules
with a version fingerprint. check() applies a generated policy to a record and
lists every violation. A specification with no rules is rejected, and a record
checked against something that is not a generated policy is non-compliant.

## Class `CSMPolicyAgent`

- `health_check()`
- `generate_policy(x)`
- `check(policy, record)` — Returns compliant and the violations. Range and allowed rules apply only when the field is present.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CSM_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_a_csm.py`, `velaris/tests/test_layer15_csm.py`
