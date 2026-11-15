# POLICY_CONTROLLER

- **Department:** `legal_compliance`
- **Status (static inventory):** `real`
- **Source:** `departments/legal_compliance/POLICY_CONTROLLER/main.py` (129 lines)

## Purpose

POLICY_CONTROLLER: a versioned policy store with a deterministic decision that names its rule.

put_policy(pid, policy) stores a new version of a policy; nothing is overwritten,
so every earlier version stays readable and evaluate() can be re-run as of any
earlier revision of the policy set. A policy that has an "effect" is a rule:

    {"effect": "allow" | "deny", "priority": int (default 0), "when": {conditions}}

with conditions as in velaris.agentkit.conditions (an absent field never
matches an allow rule and always matches a deny rule). A policy without "effect" is stored as a plain document and takes no
part in decisions. A rule-shaped policy that is malformed is refused at write time.

evaluate(context) orders the active rules by priority (highest first), then deny
before allow, then id, and the first rule whose conditions all hold decides. If
none holds, the answer is deny by the implicit "default_deny" rule. The result
always names the deciding rule, its version and the policy-set revision.

put_policy() and retire() are for governance admins only; who made a change is the
current caller (velaris.core.access), never an argument.

## Class `POLICY_CONTROLLERAgent`

- `__init__()`
- `health_check()`
- `store()` — {pid: current policy} for every policy that has not been retired.
- `put_policy(pid, policy, by)` — Store a new version of a policy, as the current caller (a governance admin).
- `retire(pid, by)` — Stop a policy taking part (its history is kept). Governance admins only.
- `get_policy(pid, version)` — The current policy (or a given version); None if absent, retired or the version does not exist.
- `history(pid)`
- `evaluate(context, at_rev)` — Decide for `context` with the rules active now, or as they stood at revision `at_rev`.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/POLICY_CONTROLLER/policies.json`

## Called by

- **other agents:** `GOVERNANCE_ADAPTATION_LOOP`, `GOVERNANCE_KERNEL`, `VIGILIS`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_legal_compliance_stubs.py`, `velaris/tests/test_governance_kernel.py`
