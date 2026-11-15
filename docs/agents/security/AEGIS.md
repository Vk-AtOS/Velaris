# AEGIS

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/AEGIS/main.py` (53 lines)

## Purpose

Aegis: per-source sliding-window rate limiting and a running threat score.
AegisAgent.record_event(source) timestamps an event and drops those older than the window (config
"window_seconds", default 10). is_rate_limited(source) is True when more than config "rate_limit"
(default 5) events fall in the window. adjust_threat(source, delta) adds to a source's score and
returns it; get_threat(source) returns the score (0 if unknown). Counting and addition only; no
blocking is enforced by this agent.
State: in-memory dicts only, nothing persisted, so limits reset on restart and are per instance.
Failure: no validation; a non-numeric delta raises TypeError.

## Class `AegisAgent`

- `__init__(config)`
- `health_check()`
- `record_event(source)`
- `is_rate_limited(source)`
- `adjust_threat(source, delta)`
- `get_threat(source)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aegis.py`, `velaris/tests/test_kan88_security_agents.py`
