# COHERENCE_SYNC_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/COHERENCE_SYNC_CORE/main.py` (75 lines)

## Purpose

Coherence sync core: detects when copies of the same state have drifted apart, and says how to fix each.

Each replica (a service, a branch office system, an agent) reports its copy of
a state. check() takes the state held by a strict majority of replicas as the
reference and, for every replica that differs, returns the patch from
CSG_STATEALIGN that would bring it back; replicas whose report is older than
`max_lag` are listed as lagging. With no majority it reports a split and
proposes nothing. Reports stamped in the future (CSG_TEMPORAL) or older than
the one already held are refused.
State: <VELARIS_DATA>/agents/COHERENCE_SYNC_CORE/state.json.

## Class `COHERENCE_SYNC_COREAgent`

- `__init__()`
- `health_check()`
- `report(replica, state, ts, now)`
- `forget(replica)`
- `check(max_lag)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.CSG_STATEALIGN.main`
- `velaris.agents.CSG_TEMPORAL.main`

## State and configuration

- state file: `<VELARIS_DATA>/agents/COHERENCE_SYNC_CORE/state.json`

## Called by

- **other agents:** `CONVERGENCE_BRIDGE`, `HYPERSYNC`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_csg.py`, `velaris/tests/test_layer28_csg.py`
