# CLOUD_HANDOFF_CONTROLLER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/it_infrastructure/CLOUD_HANDOFF_CONTROLLER/main.py` (87 lines)

## Purpose

CLOUD_HANDOFF_CONTROLLER: a durable outbox for work that has to leave this machine.

enqueue() stores an item on disk; secrets and personal identifiers in its text
are masked first (velaris.intel.guard). Only items whose "sensitivity" is on
infra_store.MAY_LEAVE_MACHINE ("public", "internal", the same list LOCAL_ROUTER uses)
are accepted; "restricted", a misspelt label or no label at all is refused. sync() delivers pending items oldest-first through a
`sender` the caller supplies, and stops at the first failure so order is kept;
an item counts as delivered only when the sender returns True.

This agent has no transport of its own and opens no connection. Without a
sender, sync() reports "not_configured" and everything stays queued: it never
claims a hand-off that did not happen.

## Class `CloudHandoffController`

- `__init__(name)`
- `health_check()`
- `enqueue(data)`
- `pending()`
- `sync(data, sender)` — Queue `data` (if given), then deliver what is pending through sender(item_data) -> bool.

## Depends on

- `velaris.agentkit`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CLOUD_HANDOFF_CONTROLLER/outbox.json`

## Called by

- **other agents:** none found
- **platform modules:** `velaris/agentkit/infra_store.py`
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer7_offline.py`
