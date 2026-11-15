# VCAS_ROUTER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/VCAS_ROUTER/main.py` (33 lines)

## Purpose

VCAS_ROUTER: can this task run on autopilot at all?

route(task, handlers) answers "autopilot" when the task is well formed and a
handler for its action is registered with the autopilot, and "manual"
otherwise (with the reason): unknown work goes to a person, never to a
default handler. It does not decide whether the task is allowed; that is
VCAS_SUPERVISOR's job. `handlers` defaults to the actions registered on a
new VCAS_AUTOPILOT, which has none.

## Class `VCASRouterAgent`

- `health_check()`
- `route(task, handlers)` — Returns autopilot_route "ok" (with the handler) or "manual" (with the reason).

## Depends on

- `velaris.agentkit.results`
- `velaris.agents.VCAS_SUPERVISOR.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `VCAS_CORE`, `VCAS_SUPERVISOR`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_b_prime_vcas.py`, `velaris/tests/test_layer19_vcas.py`
