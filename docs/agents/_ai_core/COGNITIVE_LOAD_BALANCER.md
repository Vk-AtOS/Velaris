# COGNITIVE_LOAD_BALANCER

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/COGNITIVE_LOAD_BALANCER/main.py` (38 lines)

## Purpose

Cognitive load balancer: picks which candidate agent should take a task, by lifecycle state.

LoadBalancer.choose(candidates) returns the first candidate whose LifecycleManager state is
"active", else the first candidate, else "" for an empty list. This is a plain first-match
rule, not a load measurement. health_check() reports status and version (config["version"],
default 0.1.0). Keeps no state of its own; state comes from the AGENT_LIFECYCLE_MANAGER agent.
Failure behaviour: no validation; an error from the lifecycle lookup propagates.

## Class `LoadBalancer`

- `__init__(config)`
- `health_check()`
- `choose(candidates)`

## Depends on

- `velaris.agents.AGENT_LIFECYCLE_MANAGER.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ENGINE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_ops.py`
