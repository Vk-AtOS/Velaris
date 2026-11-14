# CSM_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/CSM_CORE/main.py` (73 lines)

## Purpose

CSM core: a register of numeric goals, reviewed with the other CSM agents.

set_goal() stores a target, the time allowed and optionally a policy
specification (compiled by CSM_POLICY). review() takes the current value and
time elapsed, gets the standing and posture from CSM_REASONER, checks an
optional record against the goal's policy, and lists what the goal is linked
to in CSM_LINKER. Each review is kept, so the trend of a goal can be read back.
State: <VELARIS_DATA>/agents/CSM_CORE/state.json.

## Class `CSMCoreAgent`

- `__init__()`
- `health_check()`
- `set_goal(goal, target, total, start, policy, owner)`
- `review(goal, current, elapsed, record)`
- `goals()` — {goal: latest situation or None} for every registered goal.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.CSM_LINKER.main`
- `velaris.agents.CSM_POLICY.main`
- `velaris.agents.CSM_REASONER.main`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CSM_CORE/state.json`

## Called by

- **other agents:** `SAGE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_csm.py`, `velaris/tests/test_layer15_csm.py`
