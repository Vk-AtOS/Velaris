# COGNITIVE_INTENT_FIREWALL

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/COGNITIVE_INTENT_FIREWALL/main.py` (54 lines)

## Purpose

_No module docstring yet._

## Class `CognitiveIntentFirewall`

Velaris Cognitive Intent Firewall
- Classifies text into SAFE / RISKY / BLOCKED / UNKNOWN
- Provides rule-based forbidden term checks

- `__init__()`
- `add_rule(rule)`
- `classify(text)`
- `evaluate_rules(text)`
- `scan_untrusted(text, source)` — Screen text that came from outside (web page, document, tool output) before a model reads it.

## Depends on

- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
