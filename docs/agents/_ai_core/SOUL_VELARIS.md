# SOUL_VELARIS

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/SOUL_VELARIS/main.py` (77 lines)

## Purpose

SOUL_VELARIS: the company's charter for its agents, and the check of an action against it.

The charter is a mission statement, plain-language guidelines and guardrails.
Guardrails are rule objects (velaris.agentkit.aicore_b_rules), e.g.
{"id": "no-weekend-mail", "when": [{"field": "action", "op": "==", "value": "message.send"}],
 "require": [{"field": "day", "op": "not_in", "value": ["sat", "sun"]}]}.
The charter is versioned (who changed what, when) and stored owner-only under
this agent's state directory. Only a governance admin may change it, and the
change is recorded against the current caller (velaris.core.access), never an argument. check(action) returns the guardrails the action
breaks; with no guardrails declared nothing is "allowed" (fail closed). There
is no ethics engine here: only the rules a person wrote.

## Class `Soul`

- `__init__(config)`
- `identity()`
- `health_check()`
- `get_intent()` — The current charter: mission, guidelines, guardrails and its version number.
- `set_charter(by, mission, guidelines, guardrails)` — Change the charter as the current caller (a governance admin). `by`, if given, must be that caller.
- `check(action)` — Does `action` (an object) keep to every guardrail? allowed False lists what it breaks.
- `history()`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.aicore_b_versioned`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `FSCL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_self.py`, `velaris/tests/test_infra_agents.py`
