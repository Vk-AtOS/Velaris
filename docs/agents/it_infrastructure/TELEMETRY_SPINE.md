# TELEMETRY_SPINE

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/TELEMETRY_SPINE/main.py` (76 lines)

## Purpose

Telemetry spine: central event collector with a persistent log.
TelemetrySpine.record(event_type, payload) appends {"ts", "type", "payload"} and rewrites the log
file, returning the entry. query(event_type=None) returns all events or those of one type.
stats() returns {"total_events", "by_type"} counts. The whole log is held in memory and rewritten on
every record, so it suits low volume only.
State: <VELARIS_DATA>/agents/TELEMETRY_SPINE/telemetry.log (a JSON list, created as [] if absent).
Failure: an unreadable log is logged as a warning and treated as empty (the next record overwrites
it); a failed write raises OSError; there is no payload validation or access control.

## Class `TelemetrySpine`

Telemetry Spine
- Central event + metric collector for Velaris
- Records streams to persistent log
- Provides query + filter capabilities

- `__init__()`
- `record(event_type, payload)`
- `query(event_type)`
- `stats()`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `SYSTEM_TELEMETRY`
- **platform modules:** none found
- **tests:** `velaris/tests/test_agent_paths.py`
