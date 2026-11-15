# COMPLIANCE_GUARD

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/COMPLIANCE_GUARD/main.py` (75 lines)

## Purpose

Compliance guard: checks an action dict against registered required-field and forbidden-field rules.

add_rule(name, definition) returns False if the name exists; remove_rule(name) returns False if unknown; list_rules()
returns the names. A rule definition may hold "requires" (fields the action must contain) and "forbidden" (fields it must
not contain). evaluate(action) returns {"action", "violations": [...], "status": "OK" or "VIOLATION"}. With no rules
registered everything is OK; only field presence is checked, never values. There is no caller check.
State: in-memory rule dict only, lost on exit. A non-dict action or non-list requires/forbidden raises TypeError.

## Class `ComplianceGuard`

Velaris Compliance Guard
- Validates operations against compliance rules (kept in VELARIS_DATA, shared by every worker)
- Adding or removing a rule needs a governance admin and is traced
- Fails closed: with NO rules configured nothing is approved (status NO_RULES), never "OK"

- `__init__()`
- `rules()`
- `add_rule(name, definition)`
- `remove_rule(name)`
- `list_rules()`
- `evaluate(action)`

## Depends on

- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/COMPLIANCE_GUARD/rules.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_a.py`, `velaris/tests/test_kan88_security_agents.py`
