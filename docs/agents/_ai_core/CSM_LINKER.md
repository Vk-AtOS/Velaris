# CSM_LINKER

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/CSM_LINKER/main.py` (79 lines)

## Purpose

CSM linker: a register of named relationships between things (goals, policies, owners, accounts).

link(a, b, relation) records an undirected link once; neighbours() lists what
an item is linked to; path() finds the shortest chain of links between two
items. Items are identified by name. It stores links people or code assert; it
does not discover them.
State: <VELARIS_DATA>/agents/CSM_LINKER/state.json.

## Class `CSMLinkerAgent`

- `__init__()`
- `health_check()`
- `link(a, b, relation)` — `linked` is True when the link exists after the call; `created` is False for a repeat.
- `unlink(a, b, relation)`
- `neighbours(item, relation)`
- `path(a, b)` — Shortest chain of linked items from a to b (breadth-first), or not_found.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CSM_LINKER/state.json`

## Called by

- **other agents:** `CSM_CORE`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_a_csm.py`, `velaris/tests/test_layer15_csm.py`
