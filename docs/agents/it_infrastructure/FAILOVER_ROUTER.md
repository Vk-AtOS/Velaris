# FAILOVER_ROUTER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/FAILOVER_ROUTER/main.py` (101 lines)

## Purpose

FAILOVER_ROUTER: send a service's traffic to its first working target.

Each service has an ordered list of targets (primary first). Every target has a
circuit breaker driven by the outcomes the caller reports:

  closed      in use. `failure_threshold` consecutive failures open it.
  open        skipped until `recovery_s` has passed since it opened.
  half_open   after that wait, route() offers it again as a probe: one success
              closes it, one failure re-opens it for another full wait.

route() returns the first target in priority order that is closed or due a
probe, so traffic returns to the primary once it has recovered. With every
circuit open it answers "unavailable" rather than guess.

## Class `FAILOVER_ROUTERAgent`

- `__init__(name)`
- `health_check()`
- `configure(service, targets, failure_threshold, recovery_s)`
- `route(service, now)`
- `report(service, target, success, now)` — Tell the router how a call to `target` went.
- `status(service)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `NIRVANA`
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs.py`, `velaris/tests/test_layer8_gro.py`
