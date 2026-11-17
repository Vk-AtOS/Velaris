# CREATIVE_HOLODECK

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/CREATIVE_HOLODECK/main.py` (59 lines)

## Purpose

Creative holodeck: composes a one-sentence scene description from four fixed word lists (rule-based, not generative).

compose(style, mood, element, action) returns {style, mood, element, action, description} when each value is in its
list (styles fantasy/scifi/noir/minimal, moods bright/dark/calm/chaotic, elements forest/city/ocean/desert, actions
exploring/resting/battling/searching); otherwise {"error": "invalid_style"}, "invalid_mood", "invalid_element" or
"invalid_action" for the first value that is not. random_scene() composes from random choices (the global random
module; not seedable from here).
State: none beyond the four lists, which are per instance. Bad input returns an error dict; nothing is raised.

## Class `CreativeHolodeck`

Velaris Creative Holodeck
- Generates simple offline creative scenes
- Mixes elements, styles, moods, and actions
- Not a generative model — rule-based composition only

- `__init__()`
- `compose(style, mood, element, action)` — Creates a combined creative scene description.
- `random_scene()` — Quick random preset scene.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_agents_coverage_a.py`
