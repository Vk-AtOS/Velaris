# EACPE_PROTOCOL

- **Department:** `legal_compliance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/legal_compliance/EACPE_PROTOCOL/main.py` (96 lines)

## Purpose

EACPE_PROTOCOL: did a case follow its required procedure?

A protocol is an ordered list of required steps, for example change management:

    [{"step": "request"}, {"step": "review", "distinct_from": ["request"]},
     {"step": "approve", "distinct_from": ["request"]}, {"step": "execute"}, {"step": "verify"}]

evaluate_protocol({"protocol": name, "events": [{"step", "actor", "ts"}, ...]})
checks, deterministically:

  missing        every required step occurred
  order          each step's first occurrence comes after the previous step's
  segregation    a step marked distinct_from was done by someone other than the
                 actor(s) of the named earlier steps (four-eyes rule)
  unknown        events whose step is not in the protocol are reported

protocol_safe is True only when the protocol exists and there are no findings.
Protocols are stored on disk and can be redefined; each result names the
protocol version it was checked against.

## Class `EACPE_PROTOCOLAgent`

- `__init__()`
- `health_check()`
- `define(protocol, steps)`
- `evaluate_protocol(data)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- state file: `<VELARIS_DATA>/agents/EACPE_PROTOCOL/protocols.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_legal_compliance_stubs.py`, `velaris/tests/test_layer32_eacpe.py`
