# CONNECTOR_LAYER

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/CONNECTOR_LAYER/main.py` (75 lines)

## Purpose

Connector layer: an in-memory registry of connector configs with a simulated request.

register_connector(name, config) (False if it exists), update_connector(name, config) (merges;
False if unknown), get_connector(name) (None if unknown), remove_connector(name) (False if
unknown). request(connector_name, payload) performs no real IO: it echoes the payload as
{"status": "OK", ...} or returns {"status": "ERROR", "error": "ConnectorMissing"}. Configs are
stored as given, with no secret handling. State: a dict in memory only, lost on restart.

## Class `ConnectorLayer`

Velaris Connector Layer
- Manages external/internal service connectors
- Provides registry for adapters
- Normalizes request/response formats

- `__init__()`
- `register_connector(name, config)`
- `update_connector(name, config)`
- `get_connector(name)` — A COPY of the connector's config with secret-looking values masked; the live config never leaves this agent.
- `remove_connector(name)`
- `request(connector_name, payload)` — Simulation of a request dispatch.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan86_operations.py`
