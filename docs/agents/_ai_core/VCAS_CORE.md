# VCAS_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/VCAS_CORE/main.py` (99 lines)

## Purpose

VCAS_CORE: submit a task, and it runs on autopilot only when it is allowed to.

submit(task):
  1. VCAS_ROUTER: is there an autopilot handler?    no  -> "manual"
  2. VCAS_SUPERVISOR (PRIME): may it run?            deny -> "denied"
                                                     needs_approval -> "pending" (stored, names the approver)
  3. VCAS_AUTOPILOT runs it                          -> "done" / "failed"
decide(task_id, approve) settles a pending task: only the approver PRIME
named can decide; an approval runs the task, a rejection closes it. The decision
records the task's digest (aicore_b_authz.task_digest), so the approval covers
exactly the stored task, params included. Identity is the current caller
(velaris.core.access): submit() only for the task's own principal, decide() only
by the named approver; a legacy `by` must be the caller. Pending
tasks are stored owner-only under this agent's state directory and survive a
restart (handlers must be registered again on the new autopilot instance).

## Class `VCASCoreAgent`

- `__init__(autopilot, supervisor)`
- `health_check()`
- `submit(task, now)`
- `pending()`
- `decide(task_id, approve, by, note)`

## Depends on

- `velaris.agentkit.aicore_b_authz`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.VCAS_AUTOPILOT.main`
- `velaris.agents.VCAS_ROUTER.main`
- `velaris.agents.VCAS_SUPERVISOR.main`
- `velaris.core.access`
- `velaris.intel`

## State and configuration

- state file: `<VELARIS_DATA>/agents/VCAS_CORE/pending.json`

## Called by

- **other agents:** `ASEL_EXECUTOR`, `VCAS_AUTOPILOT`, `VCAS_SUPERVISOR`
- **platform modules:** `velaris/agentkit/aicore_b_authz.py`, `velaris/intel/approvals.py`
- **tests:** `velaris/tests/test_aicore_a_asel.py`, `velaris/tests/test_aicore_b_prime_vcas.py`, `velaris/tests/test_approval_audit.py`, `velaris/tests/test_kan95_core.py`, `velaris/tests/test_layer19_vcas.py`
