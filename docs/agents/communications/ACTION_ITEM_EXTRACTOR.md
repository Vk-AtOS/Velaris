# ACTION_ITEM_EXTRACTOR

- **Department:** `communications`
- **Status (static inventory):** `real`
- **Source:** `departments/communications/ACTION_ITEM_EXTRACTOR/main.py` (195 lines)

## Purpose

Action item extractor: finds action items in meeting text with regex rules and stores them in SQLite.

ActionItemExtractor(config): health_check(); extract_from_segments(segments, meeting_id)
takes [{"text", "start", "end"}], keeps segments matching keyword patterns (will ... by,
need to, action item, follow up, due, deadline, assign, ensure, ...), guesses an owner from
capitalised-name patterns and a due-date hint, inserts rows and returns them;
extract_from_text(text, meeting_id) splits into sentences first; close_item(item_id) marks
a row closed; get_open_items(owner=None); get_overdue() lists open items whose due_date
string sorts before today.
This is pattern matching, not language understanding; due hints can be non-ISO text
("oct 15", "friday"), which are compared as plain strings by get_overdue().
State: sqlite file action_items.db under the agent data dir (velaris.intel.paths.agent_file).
Failure: segments without a match are skipped; close_item on an unknown id still returns
status closed.

## Class `ActionItemExtractor`

Extracts structured action items from meeting transcripts or text,
inferring owner and due-date hints from natural language patterns.
Creates tasks in local SQLite; ready to integrate with Zoho Projects or Jira.

- `__init__(config)`
- `health_check()`
- `extract_from_segments(segments, meeting_id)` — segments: list of {"text": "...", "start": 0.0, "end": 5.0}
- `extract_from_text(text, meeting_id)` — Convenience: split text into pseudo-segments and extract.
- `close_item(item_id)`
- `get_open_items(owner)`
- `get_overdue()`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_no_state_in_source_tree.py`
