# AGENT_EVOLUTION

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/AGENT_EVOLUTION/main.py` (38 lines)

## Purpose

Agent evolution: records per-agent metrics and proposes a tuning action from a trivial count heuristic.
EvolutionEngine.record(agent_name, metric) appends a metric dict to an in-memory list for that agent.
propose(agent_name) returns {"agent", "proposal"}: "tune-params" when more than 5 metrics are recorded
for the agent, otherwise "none". This is a stub heuristic (it never reads the metric values).
health_check() returns {"agent", "status": "ok", "version"}.
State: in-memory dict only, nothing persisted. Failure: no validation; an unknown agent gives "none",
and a non-dict config raises from config.get.

## Class `EvolutionEngine`

- `__init__(config)`
- `health_check()`
- `record(agent_name, metric)`
- `propose(agent_name)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_a.py`
