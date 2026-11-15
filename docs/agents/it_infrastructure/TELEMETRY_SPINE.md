# TELEMETRY_SPINE

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/TELEMETRY_SPINE/main.py` (72 lines)

## Purpose

_No module docstring yet._

## Class `TelemetrySpine`

Telemetry Spine
- Central event + metric collector for Velaris
- Appends one JSON line per event (owner-only, locked across workers, a bad payload cannot damage
  earlier events); payloads are redacted of secrets and personal identifiers and size-bounded
- Provides query + filter capabilities over the newest events

- `__init__()`
- `events()`
- `record(event_type, payload)` — The stored entry, or None when the event is not a name plus a JSON object of reasonable size.
- `query(event_type)`
- `stats()`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.state`
- `velaris.core.filelock`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `SYSTEM_TELEMETRY`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan90_infra.py`
