# INITIATIVE_ENGINE

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/INITIATIVE_ENGINE/main.py` (70 lines)

## Purpose

INITIATIVE_ENGINE: rank proposed initiatives by RICE and keep the register.

propose(context) reads context["initiatives"], each
    {"name", "reach", "impact", "confidence" (0-1), "effort" (> 0, e.g. person-weeks)}
and scores it with the standard RICE formula:

    RICE = reach x impact x confidence / effort

The ranked list is returned (highest first, ties by name) and saved, so the
last ranking survives a restart (`register()`). The inputs are the proposer's
own estimates: the engine orders them, it does not generate initiatives or
judge whether the estimates are right. No initiatives -> `needs_data`.
State: <VELARIS_DATA>/agents/INITIATIVE_ENGINE/register.json (owner-only).

## Class `InitiativeEngine`

- `__init__(name)`
- `health_check()`
- `propose(context)`
- `register()` — The last saved ranking.

## Depends on

- `velaris.agentkit`

## State and configuration

- state file: `<VELARIS_DATA>/agents/INITIATIVE_ENGINE/register.json`

## Called by

- **other agents:** `AIIE_KERNEL`
- **platform modules:** none found
- **tests:** `velaris/tests/test_AI_IE_layer.py`, `velaris/tests/test_dept_project_management_stubs.py`
