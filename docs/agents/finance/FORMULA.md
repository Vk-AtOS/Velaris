# FORMULA

- **Department:** `finance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/finance/FORMULA/main.py` (51 lines)

## Purpose

Formula: builds a framework dict, scores pattern variety and shallow-merges templates (trivial helpers).

FormulaAgent(config; "weight" default 1.0): health_check(); build_framework(title,
pillars) returns {"title", "pillars"}; pattern_score(elements) = number of unique
elements * weight; merge_templates(t1, t2) returns {**t1, **t2}, t2 winning on conflicts.
State: keeps no state beyond the configured weight.
Failure: no validation; unhashable elements raise TypeError and non-dict templates raise
TypeError.

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
