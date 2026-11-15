# COMPUTE_SCALER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/COMPUTE_SCALER/main.py` (79 lines)

## Purpose

COMPUTE_SCALER: decides how many replicas a workload group should have.

Target tracking, the same rule most autoscalers use:

    desired = ceil(current * utilization / target)      clamped to [min, max]

with two guards against flapping: no change while utilization is within
`tolerance` of the target, and no scale-down until `cooldown_s` has passed since
the last change (scale-up is never delayed). decide() records the decision and
returns it; it launches and stops nothing. Whoever owns the replicas applies it.

## Class `COMPUTE_SCALERAgent`

- `__init__(name)`
- `health_check()`
- `set_policy(group, min_replicas, max_replicas, target_utilization, cooldown_s)`
- `decide(group, current_replicas, utilization, now)` — Scale `group` up, down or hold, given its replica count and average utilization (percent).

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs.py`, `velaris/tests/test_layer8_gro.py`
