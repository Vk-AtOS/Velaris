# MCFE_ROUTER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/MCFE_ROUTER/main.py` (36 lines)

## Purpose

MCFE_ROUTER: which department handles a subject domain.

route(domain) looks the domain up in a fixed table and confirms that the
department exists under departments/. A domain with no department here
(medical) or an unknown domain is "unrouted": it goes to a person, not to a
default department.

## Class `MCFERouterAgent`

- `health_check()`
- `route(domain)` — Returns route "ok" with the department, or route "unrouted" with the reason.

## Depends on

- `velaris.agentkit.results`
- `velaris.agents`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MCFE_CLASSIFIER`, `MCFE_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_aicore_b_mcfe.py`, `velaris/tests/test_layer18_mcfe.py`
