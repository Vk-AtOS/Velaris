# AUTONOMOUS_RESEARCH_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/AUTONOMOUS_RESEARCH_ENGINE/main.py` (98 lines)

## Purpose

Autonomous research engine: ranks documents in registered in-memory sources by keyword match, and delegates live-web research to velaris.intel.research.

AutonomousResearchEngine: register_source(name) creates an empty lowercase-keyed source
(False if it exists); add_document(source, data) appends a dict (False if the source is
unknown); query(term) scores each document by how many of its fields contain the term
(case-insensitive substring) and returns matches best first; summarize(results) joins the
top 3 into one string with a count ("No results", 0 for an empty list); research(question,
**limits) returns velaris.intel.research.research(...).to_dict() and takes max_subquestions,
max_sources, max_rounds.
State: in memory only (self.sources), lost on restart; research() keeps none here.
Failure: bad names or sources return False or empty results; query() on a non-string term
raises AttributeError; research() errors propagate from velaris.intel.research.

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
- **platform modules:** `velaris/api/allowlist.py`, `velaris/intel/tools.py`
- **tests:** `velaris/tests/test_agents_coverage_a.py`
