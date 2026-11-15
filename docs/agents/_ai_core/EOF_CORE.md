# EOF_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/EOF_CORE/main.py` (93 lines)

## Purpose

EOF_CORE: turns a plan into ordered, policy-checked hand-offs.

orchestrate(plan) validates the steps, orders them by their dependencies
(cycles and unknown dependencies are errors), checks every step against the
policy if one is given (EOF_POLICY), and only when all of that passes queues
each step for its target through EOF_GATEWAY, as itself (`via=self`) on behalf of
the current caller, who must be authenticated. All or nothing: a plan with one
bad step dispatches no step. It orders and hands off; it does not run the
steps or wait for them.

A plan is either one step {"task", "target", ...} or
{"steps": [{"id", "task", "target", "depends_on": [...], "payload": {...}}]}.

## Class `EOF_COREAgent`

- `__init__()`
- `health_check()`
- `orchestrate(plan, policy)` — Returns result "ok" (all steps queued), "invalid", "blocked" (policy) or "failed" (hand-off).

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agents.EOF_GATEWAY.main`
- `velaris.agents.EOF_POLICY.main`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CORE_CONVERGENCE`, `EOF_POLICY`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_eof.py`, `velaris/tests/test_layer31_eof.py`
