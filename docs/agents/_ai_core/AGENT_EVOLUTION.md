# AGENT_EVOLUTION

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/AGENT_EVOLUTION/main.py` (55 lines)

## Purpose

Agent evolution: records per-agent metrics and proposes a tuning action when a cost metric is getting worse.
EvolutionEngine.record(agent_name, metric) keeps a dict of numbers for the agent (at most 200 per agent, 1,000 agents; a
bad name or a metric that is not a dict of finite numbers returns {"ok": False, "reason": ...} and records nothing).
propose(agent_name) returns {"agent", "proposal"}: "tune-params" when more than 5 metrics are recorded and the mean of
a cost metric ("loss", "error", "errors", "latency", "cost") over the newer half is higher than over the older half,
otherwise "none". The metric values ARE read: a steady or improving agent is never proposed for tuning. This is still
a heuristic; it proposes, it changes nothing.
health_check() returns {"agent", "status": "ok", "version"}.
State: in-memory dict only, nothing persisted. A non-dict config is treated as empty.

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
- **tests:** `velaris/tests/test_agents_coverage_a.py`, `velaris/tests/test_r3_patch_evolution_search_clbpp.py`
