# FORMULA

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/FORMULA/main.py` (45 lines)

## Purpose

_No module docstring yet._

## Class `FormulaAgent`

- `__init__(config)`
- `health_check()`
- `build_framework(title, pillars)` — Returns structured framework with title + pillars.
- `pattern_score(elements)` — Score = count of unique items * weight
- `merge_templates(t1, t2)` — Merge two templates shallowly.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_formula.py`
