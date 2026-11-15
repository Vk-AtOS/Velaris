# COMPLIANCE_GUARD

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/COMPLIANCE_GUARD/main.py` (78 lines)

## Purpose

Compliance guard: checks an action dict against registered required-field and forbidden-field rules.

add_rule(name, definition) and remove_rule(name) need a governance admin (check_caller, traced) and return False when
refused; add_rule also returns False for a duplicate name, for more than 500 rules, and for a definition that is not a
dict holding only "requires" and/or "forbidden", each a non-empty list of field names. list_rules() returns the names.
evaluate(action) returns {"action", "violations": [...], "status"}: "OK" or "VIOLATION" against the rules, "NO_RULES"
when none are registered (an empty rule set approves nothing), and "VIOLATION" for an action that is not a dict. Only
field presence is checked, never values. Evaluating needs no caller.
State: <VELARIS_DATA>/agents/COMPLIANCE_GUARD/rules.json, owner-only and shared by every worker. Bad input is refused
with False or a status; nothing is raised.

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
