# ACTION_ITEM_EXTRACTOR

- **Department:** `communications`
- **Status (static inventory):** `real`
- **Source:** `departments/communications/ACTION_ITEM_EXTRACTOR/main.py` (190 lines)

## Purpose

Action item extractor: finds action items in meeting text with fixed regex patterns and stores them (no LLM).

extract_from_segments(segments, meeting_id="") keeps each {"text", "start", "end"} segment that matches an action phrase
("will ... by", "needs to", "follow up", "deadline", ...), guesses an owner from patterns such as "Asha will" or
"assigned to Asha", and a due date: an ISO date after "by", today / tomorrow / next week resolved to ISO dates, or a text
hint such as "oct 15" or "friday" kept as written. Each item is saved and returned as {id, text, owner, due_date, status,
meeting_id}. extract_from_text(text, meeting_id="") splits the text into sentences first. close_item(item_id) marks an
item closed (an unknown id is not reported). get_open_items(owner=None) lists open items; get_overdue() lists open items
whose due date is an ISO date before today (a text hint is never overdue). health_check() returns status ok.
State: sqlite <VELARIS_DATA>/agents/ACTION_ITEM_EXTRACTOR/action_items.db (table action_items). No caller check is made.
Failure: a segment that is not a dict, or non-text input, raises AttributeError or TypeError; sqlite errors propagate.

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

- `velaris.core.sqlite_util`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_kan93_agents.py`, `velaris/tests/test_no_state_in_source_tree.py`
