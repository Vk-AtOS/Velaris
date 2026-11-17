# LEGAL_INTELLIGENCE_ENGINE

- **Department:** `legal_compliance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/legal_compliance/LEGAL_INTELLIGENCE_ENGINE/main.py` (67 lines)

## Purpose

Legal intelligence engine: an in-memory store of legal rule texts with exact lookup and keyword search.

Rules are kept as category -> rule -> text; category and rule names are lower-cased. add_rule(category, rule, text) returns
False if that rule already exists, update_rule(...) returns False if the category or rule is missing, lookup(category, rule)
returns the text or the string "NOT_FOUND". search(keyword) does a case-insensitive substring match on rule names and texts
and returns "category:rule" strings. It holds no built-in rules and gives no legal advice or interpretation.
State: in-memory dicts only, lost on exit. A non-string argument raises AttributeError.

## Class `LegalIntelligenceEngine`

Velaris Legal Intelligence Engine (Offline)
- Stores simplified legal rules as key → text
- Performs keyword searches
- Category-based rule grouping

- `__init__()`
- `add_rule(category, rule, text)`
- `update_rule(category, rule, text)`
- `lookup(category, rule)`
- `search(keyword)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_a.py`, `velaris/tests/test_allowlist_departments.py`
