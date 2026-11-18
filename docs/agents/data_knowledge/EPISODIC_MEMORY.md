# EPISODIC_MEMORY

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/EPISODIC_MEMORY/main.py` (98 lines)

## Purpose

EPISODIC_MEMORY: a durable, time-ordered log of what happened.

An episode is one event described by the caller: who did what, with what
outcome ({"actor": ..., "summary": ..., "tags": [...], ...}). record() stamps it
with an id and a time and masks secrets and personal identifiers in its text
(velaris.intel.guard) before it is written. list_episodes() answers "what
happened between these times / by this actor / with this tag".

consolidate() hands the summaries of episodes not yet consolidated to long-term
memory (velaris.intel.memory), which turns them into durable facts. The episode file is locked only to claim the
episodes (for CLAIM_SECONDS, so a second consolidate skips them) and again to mark them done, never while the model
runs, so record() is not blocked by a slow consolidation; a failed consolidation releases its claim. Episodes
themselves are never edited or deleted; only the oldest fall off after MAX_EPISODES.

## Class `EPISODIC_MEMORYAgent`

- `__init__()`
- `health_check()`
- `record(episode, now)`
- `list_episodes(since, until, actor, tag, limit)` — Episodes in time order, filtered. `since` is inclusive, `until` exclusive; limit keeps the newest.
- `consolidate(scope, source)` — Turn the "summary" of each not-yet-consolidated episode into long-term facts under `scope`.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/EPISODIC_MEMORY/episodes.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_harness.py`, `velaris/tests/test_dept_data_knowledge_stubs.py`, `velaris/tests/test_memory_substrate.py`, `velaris/tests/test_r3_memory_dna.py`
