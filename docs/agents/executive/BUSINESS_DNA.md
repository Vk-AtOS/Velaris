# BUSINESS_DNA

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/BUSINESS_DNA/main.py` (83 lines)

## Purpose

BUSINESS_DNA: the company profile register.

"DNA" here means the handful of facts other agents and documents should agree
on: who the company is, what it sells and to whom. The agent validates a
profile, stores it with a version number, returns it, and reports which
required fields are still missing. It does not analyse or infer anything.

run(payload):
  {"action": "set", "profile": {...}}   validate, merge over the stored profile, save
  {"action": "get"}                     the stored profile, its version and missing fields

State: <VELARIS_DATA>/agents/BUSINESS_DNA/profile.json (owner-only; a set is one locked read-merge-write, so two
workers setting different fields both survive).

## Class `BusinessDnaAgent`

- `__init__(config)`
- `health_check()`
- `run(payload)`

## Depends on

- `velaris.agentkit`

## State and configuration

- state file: `<VELARIS_DATA>/agents/BUSINESS_DNA/profile.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_executive_stubs.py`, `velaris/tests/test_r3_memory_dna.py`
