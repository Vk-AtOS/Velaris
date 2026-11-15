# COGNITIVE_INTENT_FIREWALL

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/COGNITIVE_INTENT_FIREWALL/main.py` (75 lines)

## Purpose

Cognitive intent firewall: keyword classification of text, plus a prompt-injection scan of untrusted content.

classify(text) returns {"intent", "reason"}: BLOCKED if a blocked keyword (harm, attack, illegal, kill) starts any word,
else RISKY (bypass, override, exploit), else SAFE (help, info, guide, learn), else UNKNOWN; non-text is UNKNOWN. Matching
is on word starts, so "attacker" matches "attack" and "skill" does not match "kill". add_rule(rule) registers a dict;
evaluate_rules(text) returns "Forbidden content: <term>" for each rule["forbidden"] term found as a substring, ignoring
case. scan_untrusted(text, source="") runs velaris.intel.guard.scan and returns {level, blocked, score, findings}.
This is a keyword list, not an understanding of intent: it is easy to phrase around and must not be the only control.
State: keyword lists and rules in memory, per instance. Failure: evaluate_rules raises AttributeError for non-text; rules
are not validated, and no caller check is made.

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
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan88_security_agents.py`
