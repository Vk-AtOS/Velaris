# VCAS_SUPERVISOR

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/VCAS_SUPERVISOR/main.py` (54 lines)

## Purpose

VCAS_SUPERVISOR: says whether a task may run, by asking PRIME.

VCAS is read here as "Velaris controlled autopilot": VCAS_ROUTER decides
whether a task can run on autopilot at all, VCAS_SUPERVISOR decides whether it
is allowed, VCAS_AUTOPILOT runs it, VCAS_CORE runs the whole flow including
waiting for a person.

This agent holds no rules of its own: approve(task) is PRIME.authorize for the
task's principal, action, resource and context. approved is True only for
"allow"; "needs_approval" names the person who must decide; anything else is a
refusal.

task: {"id", "action", "principal", "resource" (optional), "context": {"amount", "currency"} (optional),
       "params": {...} (optional)}

## Class `VCASSupervisorAgent`

- `__init__(prime)`
- `health_check()`
- `approve(task, now)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agents.PRIME.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `VCAS_AUTOPILOT`, `VCAS_CORE`, `VCAS_ROUTER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_prime_vcas.py`, `velaris/tests/test_approval_audit.py`, `velaris/tests/test_kan95_core.py`, `velaris/tests/test_layer19_vcas.py`
