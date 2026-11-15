# ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ENGINE/main.py` (99 lines)

## Purpose

Velaris engine: runs methods of registered agents by name, singly or as a pipeline.
VelarisEngine.run(agent, method, params) creates the agent through AgentRegistry.create and calls the
method with params as keyword arguments. pipeline(steps) runs a list of {"agent", "method", "params"}
steps in order and returns [{"step", "result"}]. run_with_balance is a plain passthrough to run (the
load balancer is not consulted). health_check() reports the number of registered agents.
State: keeps none of its own beyond the registry instance; parameters and results are never logged.
Failure: an unknown agent propagates the registry's error, a missing, non-callable or private ("_"-prefixed) method raises AttributeError, and
an exception from the agent or a malformed pipeline step (KeyError) propagates and stops the pipeline.
Note: self.lifecycle and self.clb are created in __init__, but run() does not consult them.

## Class `VelarisEngine`

Central execution engine for all Velaris operations.
Loads agents through the REGISTRY and executes their methods dynamically.
Provides:
    - run(agent_name, method, params)
    - pipeline([{agent, method, params}, ...])
    - health_check()

- `__init__(config)`
- `health_check()`
- `run(agent, method, params)`
- `pipeline(steps)` — steps = [
- `run_with_balance(agent, method, params)`

## Depends on

- `velaris.agents.AGENT_LIFECYCLE_MANAGER.main`
- `velaris.agents.COGNITIVE_LOAD_BALANCER.main`
- `velaris.agents.REGISTRY.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CORE_CONVERGENCE`, `FSCL`, `PRIME`
- **platform modules:** `velaris/backend/engine.py`
- **tests:** `velaris/tests/test_engine.py`, `velaris/tests/test_kan106_intake_guards.py`, `velaris/tests/test_kan87_aicore_guards.py`, `velaris/tests/test_system_integration.py`
