# AUTONOMOUS_RESEARCH_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/AUTONOMOUS_RESEARCH_ENGINE/main.py` (84 lines)

## Purpose

_No module docstring yet._

## Class `AutonomousResearchEngine`

Velaris Autonomous Research Engine (Offline)
- Accepts research queries
- Searches across registered offline datasets
- Performs scoring + ranking
- Produces structured offline "research summaries"

- `__init__()`
- `register_source(name)`
- `add_document(source, data)`
- `query(term)` — Simple offline research:
- `research(question, **limits)` — Research a question on the live web. Every sentence of the report cites a source,
- `summarize(results)`

## Depends on

- `velaris.intel.research`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** none found
