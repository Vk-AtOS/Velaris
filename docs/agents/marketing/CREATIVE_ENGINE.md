# CREATIVE_ENGINE

- **Department:** `marketing`
- **Status (static inventory):** `real`
- **Source:** `departments/marketing/CREATIVE_ENGINE/main.py` (96 lines)

## Purpose

CREATIVE_ENGINE: campaign ideas, variations and blends, drafted by a model.

  generate_idea(theme)        one concrete idea for the theme
  variations(base, count)     `count` distinct rewrites of a line
  blend(a, b)                 one concept combining two

The drafting is done by a language model through velaris.intel.llm; code checks
each reply (non-empty, the requested number of distinct items, not blocked by
the guard) and screens the caller's text before it reaches a prompt. Without a
model nothing is made up: generate_idea returns `not_configured` with no idea,
variations returns [] and blend returns "" (see `last_status`).

There is no quality score: `creative_score` stays None because nothing here can
measure how good an idea is. History of accepted ideas is kept at
<VELARIS_DATA>/agents/CREATIVE_ENGINE/history.json (owner-only).

## Class `CreativeEngine`

- `__init__(llm)`
- `health_check()`
- `generate_idea(theme)`
- `variations(base, count)`
- `blend(a, b)`
- `get_history()`

## Depends on

- `velaris.agentkit`
- `velaris.intel.llm`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CREATIVE_ENGINE/history.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_marketing_stubs.py`
