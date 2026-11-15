# PRIME

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/PRIME/main.py` (206 lines)

## Purpose

PRIME: the Velaris controller, and the one place that decides what an agent or person may do.

Two jobs.
1. Authorisation (written fresh for Velaris after the shape of AetherOS Prime):
   authorize(principal, action, resource, context) -> allow / needs_approval / deny
   with a reason, from time-limited grants that people give. The decision is
   pure code over the stored grants (velaris.agentkit.aicore_b_authz): no model,
   fail closed, a NEVER list no grant can open, a hard amount ceiling, and
   anything a grant does not clearly cover goes to the grant's named approver.
   Grants are stored owner-only under this agent's state directory. Every
   grant, revocation, request and decision is written to the hash-chained trace
   before the answer is returned; if the trace cannot be written the answer is deny.
2. Control of the engine (kept from before): system_status(), a self-test
   pipeline, and execute(agent, method), which runs only when a grant allows the
   current caller "agent.execute" on exactly "<AGENT>.<method>" (an explicit
   allowlist; no patterns). Private methods, PRIME itself and governance
   management methods (MANAGEMENT_METHODS) are never run through execute.

Identity comes from the current caller (velaris.core.access), never an argument:
grant() is given by the caller, who must be a governance admin or hold a live,
delegable grant covering everything they pass on (never more than they hold), and
may not grant to themselves; revoke() is for the grantor, the approver or a
governance admin. A legacy grantor/by/principal argument must name the caller.

## Class `VelarisPrime`

- `__init__(config)`
- `engine()` — The agent engine, built on first use (it scans every department).
- `health_check()`
- `system_status()` — Diagnostics across PRIME + ENGINE + REGISTRY.
- `run_simple_self_test()` — Health of the three security agents, through the engine pipeline.
- `execute(agent, method, params, principal)` — Run agent.method(**params) for the current caller, only if a grant names exactly that method.
- `grant(grantor, principal, actions, approver, resources, autonomy, valid_for_seconds, max_amount, currency, delegable, now)` — Record a grant from the current caller to `principal`. Returns its id, or why it was refused.
- `revoke(grant_id, by, now)` — The grantor, the named approver or a governance admin (the current caller) can revoke a grant.
- `grants(principal, live_only)`
- `authorize(principal, action, resource, context, now, task_id, params)` — allow / needs_approval / deny with a reason. Both the request and the decision are traced first.

## Class `PrimeAgent`

Backward-compatible alias (test_phase4_intel.py and integration tests use this name).


## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.ENGINE.main`
- `velaris.core.access`
- `velaris.intel`

## State and configuration

- state file: `<VELARIS_DATA>/agents/PRIME/grants.json`

## Called by

- **other agents:** `ASEL_EXECUTOR`, `ENGINE`, `FSCL`, `VCAS_AUTOPILOT`, `VCAS_CORE`, `VCAS_SUPERVISOR`
- **platform modules:** `velaris/agentkit/aicore_b_authz.py`, `velaris/core/access.py`
- **tests:** `velaris/tests/test_aicore_a_ops.py`, `velaris/tests/test_aicore_b_eof.py`, `velaris/tests/test_aicore_b_prime_vcas.py`, `velaris/tests/test_kan95_core.py`, `velaris/tests/test_layer31_eof.py`, `velaris/tests/test_phase4_intel.py`, `velaris/tests/test_prime.py`
