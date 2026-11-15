# COGNITIVE_INTENT_FIREWALL

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/COGNITIVE_INTENT_FIREWALL/main.py` (66 lines)

## Purpose

Cognitive intent firewall: keyword-based intent classification and screening of untrusted text.
CognitiveIntentFirewall.classify(text) checks substrings in order and returns {"intent", "reason"}:
BLOCKED for harm/attack/illegal/kill, RISKY for bypass/override/exploit, SAFE for
help/info/guide/learn, else UNKNOWN. Plain substring matching, so it is easy to evade and also
matches inside longer words. add_rule(rule) stores a rule dict and evaluate_rules(text) returns
"Forbidden content: <term>" for each term of each rule's "forbidden" list found in the text.
scan_untrusted(text, source="") delegates to velaris.intel.guard.scan and returns level, blocked,
score and findings.
State: rules are in memory only, nothing persisted. Failure: classify and evaluate_rules raise
AttributeError for non-string text; a rule without "forbidden" is ignored; the guard's own errors
propagate.

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
- **tests:** `velaris/tests/test_agents_coverage_c.py`
