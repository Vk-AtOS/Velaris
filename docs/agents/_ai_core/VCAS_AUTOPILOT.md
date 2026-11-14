# VCAS_AUTOPILOT

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/VCAS_AUTOPILOT/main.py` (116 lines)

## Purpose

VCAS_AUTOPILOT: runs a task through a registered handler, once, and only with an approval.

register(action, handler) adds a Python callable taking the task's params and
returning a JSON-able result. execute(task, approval) runs it only when
`approval` carries the trace hash of either PRIME's "allow" decision or VCAS_CORE's
record of a person approving, and that decision carries the same
aicore_b_authz.task_digest as the task given here: id, action, principal,
resource, context (amount, currency ...) and params, so nothing the handler
receives can differ from what was approved. The run is also bound to the caller
(velaris.core.access): a PRIME allow runs only for the task's principal, a
person's approval only for that person. The hash is looked up in the
trace, so an approval cannot be made up by the caller, and each hash is
spent once (kept in the same state file), so it cannot be replayed. A task id that
already ran is never run again: the stored result is returned instead
(state under this agent's state directory, survives restart). Handler errors
are caught and recorded as a failed run. Every run is written to the trace.
ponytail: handlers live in the process; after a restart callers register them
again. A task that crashed the process mid-run is marked "started" and needs a
person to decide whether to run it again.

## Class `VCASAutopilotAgent`

- `__init__()`
- `health_check()`
- `register(action, handler)`
- `handlers()`
- `run_of(task_id)`
- `execute(task, approval)`

## Depends on

- `velaris.agentkit.aicore_b_authz`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.VCAS_SUPERVISOR.main`
- `velaris.core.access`
- `velaris.intel`

## State and configuration

- state file: `<VELARIS_DATA>/agents/VCAS_AUTOPILOT/runs.json`

## Called by

- **other agents:** `PRIME`, `VCAS_CORE`, `VCAS_ROUTER`, `VCAS_SUPERVISOR`
- **platform modules:** `velaris/agentkit/aicore_b_authz.py`
- **tests:** `velaris/tests/test_aicore_b_prime_vcas.py`, `velaris/tests/test_layer19_vcas.py`
