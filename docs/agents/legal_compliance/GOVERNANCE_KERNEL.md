# GOVERNANCE_KERNEL

- **Department:** `legal_compliance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/legal_compliance/GOVERNANCE_KERNEL/main.py` (44 lines)

## Purpose

GOVERNANCE_KERNEL: a thin front door to POLICY_CONTROLLER's versioned policy store and decision.

register_policy(pid, rule) stores a new version of a policy through
POLICY_CONTROLLER.put_policy, so it needs a governance admin as the current caller
(velaris.core.access) and the decision is traced either way.

evaluate_request(pid, request) asks POLICY_CONTROLLER.evaluate for a decision over
the whole active rule set and returns True only when that decision is "allow" and
the rule that decided it is `pid`. A plain document (a policy without "effect"),
an unknown or retired policy, a higher-priority deny, or no rule matching at all
is False.

## Class `GOVERNANCE_KERNELAgent`

- `__init__()`
- `health_check()`
- `policies()`
- `register_policy(pid, rule)` — Store a policy version. Governance admins only (checked and traced by POLICY_CONTROLLER).
- `decide(request)` — POLICY_CONTROLLER's full decision for `request`: decision, deciding rule, its version, revision.
- `evaluate_request(pid, req)`

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.POLICY_CONTROLLER.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_governance_kernel.py`
