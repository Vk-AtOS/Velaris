# CCSF_CORE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/CCSF_CORE/main.py` (60 lines)

## Purpose

CCSF core: one agreed view of an entity that several systems each hold a copy of.

ingest() stores the latest snapshot each system reported for an entity (an
older snapshot than the one held is refused as stale). view() merges the
snapshots with CCSF_FUSION, settles disagreements with CCSF_RESOLVER using the
configured strategies, and returns the agreed state, where each field came
from, and the fields still waiting for a person.
State: <VELARIS_DATA>/agents/CCSF_CORE/state.json.

## Class `CCSF_COREAgent`

- `__init__(strategies, default_strategy)`
- `health_check()`
- `ingest(entity, source, data, ts)`
- `view(entity)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.agents.CCSF_FUSION.main`
- `velaris.agents.CCSF_RESOLVER.main`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CCSF_CORE/state.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_ccsf.py`, `velaris/tests/test_layer22_ccsf.py`
