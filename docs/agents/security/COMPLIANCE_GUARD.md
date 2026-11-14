# COMPLIANCE_GUARD

- **Department:** `security`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/security/COMPLIANCE_GUARD/main.py` (45 lines)

## Purpose

_No module docstring yet._

## Class `ComplianceGuard`

Velaris Compliance Guard
- Validates operations against compliance rules
- Maintains rule registry
- Evaluates actions for violations

- `__init__()`
- `add_rule(name, definition)`
- `remove_rule(name)`
- `list_rules()`
- `evaluate(action)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
