# THREAT_DETECTION_MESH

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/THREAT_DETECTION_MESH/main.py` (74 lines)

## Purpose

Threat detection mesh: rule-based event scorer that counts matches against registered signatures; not machine learning.

ThreatDetectionMesh: add_signature(name, pattern) registers a {key: value} pattern (False
if the name exists); record_event(event) stores an event; score_event(event) adds 10 per field of
every signature whose fields ALL equal the event's values (a partial match adds nothing); detect(event) returns {event,
score, level} with level HIGH (score >= 20), MEDIUM (>= 10) or LOW; summary() rates all
recorded events.
State: in memory only (self.signatures, self.events), lost on restart; events grow without
bound.
Failure: no match gives score 0 / LOW; non-dict events raise TypeError or AttributeError.

## Class `ThreatDetectionMesh`

Velaris Threat Detection Mesh
- Detects anomalies in component behavior
- Maintains a threat signature database
- Scores incoming events for threat likelihood

- `__init__()`
- `add_signature(name, pattern)` — Register a threat pattern.
- `record_event(event)` — Record an observed event.
- `score_event(event)` — Score event severity: 10 per field of every signature that matches in full.
- `detect(event)` — Return threat rating for a single event.
- `summary()` — Summarize all events with threat scoring.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_a.py`, `velaris/tests/test_kan88_security_agents.py`
