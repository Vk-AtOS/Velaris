# TELEMETRY_SPINE

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/TELEMETRY_SPINE/main.py` (82 lines)

## Purpose

Telemetry spine: an append-only local log of typed events with a simple query and per-type counts.

record(event_type, payload) appends {"ts", "type", "payload"} as one JSON line and returns the entry; the payload is
first redacted of secrets and personal identifiers (velaris.agentkit.infra_store.redact_json). It returns None and writes
nothing when event_type is not a plain name, the payload is not a JSON-serialisable dict, or the entry is over 16 KiB.
query(event_type=None) returns the newest 10,000 events, optionally of one type; stats() counts them by type.
State: <VELARIS_DATA>/agents/TELEMETRY_SPINE/telemetry.jsonl, owner-only and locked across workers. Beyond 20 MiB the
file is renamed to telemetry.jsonl.1 (one generation kept) and a new one starts, so older events leave query(). A torn
last line is skipped on read. No caller check is made.

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
