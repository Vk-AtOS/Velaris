# IT_INFRA_ENGINE

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/IT_INFRA_ENGINE/main.py` (129 lines)

## Purpose

IT_INFRA_ENGINE: validate an infrastructure request, plan it, and judge reported VM health.

No cloud account is attached to this agent, so provision() creates nothing. It
checks the request and stores a deterministic plan: VM names, one address per
VM taken in order from the network's usable hosts, and the totals implied by
VM_SIZES (a sizing table declared here, not a provider's catalogue). The result
says "planned" - the plan is what an operator or a provider integration applies.

health_check(infra_id, vms) compares what the caller reports about the VMs with
the stored plan:

    healthy    every planned VM is reported and running
    degraded   at least one, but not all, planned VMs are running
    down       none are running

health_check() with no arguments is the agent's own liveness answer.

## Class `InfraConfig`


## Class `ITInfraEngine`

- `__init__()`
- `validate_config(cfg)`
- `provision(cfg)` — Validate and store a plan. Nothing is created: the status is "planned".
- `get_plan(infra_id)`
- `health_check(infra_id, vms)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/IT_INFRA_ENGINE/plans.json`

## Called by

- **other agents:** `LYRA_VOICE_ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_r3_voice_sim_lang.py`
