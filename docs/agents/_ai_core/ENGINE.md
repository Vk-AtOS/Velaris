# ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/ENGINE/main.py` (89 lines)

## Purpose

_No module docstring yet._

## Class `VelarisEngine`

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
- **tests:** `velaris/tests/test_engine.py`, `velaris/tests/test_kan106_intake_guards.py`, `velaris/tests/test_system_integration.py`
