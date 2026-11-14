# GOVERNANCE_ADAPTATION_LOOP

- **Department:** `legal_compliance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/legal_compliance/GOVERNANCE_ADAPTATION_LOOP/main.py` (114 lines)

## Purpose

GOVERNANCE_ADAPTATION_LOOP: learns from human overrides which rules need review. Proposes; never applies.

Every time a person overrides an automated decision, that is evidence the rule
behind it may be wrong. record() stores outcomes {"rule", "decision",
"overridden": bool}. adapt() computes, per rule with at least MIN_SAMPLES outcomes:

    override_rate = overridden / total
    >= REVIEW_RATE        proposal "review_rule"  (people disagree with it often)
    == 0 and >= 4x MIN    proposal "keep"         (consistently accepted)

A proposal only becomes "accepted" when a governance admin (the caller) accepts it with
resolve(); even then this agent changes no rule. The owner of the policy
(POLICY_CONTROLLER) makes the change. Outcomes and proposals persist.

## Class `GovernanceAdaptationLoop`

- `__init__(name)`
- `health_check()`
- `record(outcomes)`
- `adapt(shaped)` — Record any shaped["outcomes"], then return the current proposals.
- `resolve(proposal_id, accept, by)` — The current caller, a governance admin, accepts or rejects a proposal. Nothing else changes.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_legal_compliance_stubs.py`, `velaris/tests/test_layer5_neuralgov.py`
