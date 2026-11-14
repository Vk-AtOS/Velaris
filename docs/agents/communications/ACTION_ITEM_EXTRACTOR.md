# ACTION_ITEM_EXTRACTOR

- **Department:** `communications`
- **Status (static inventory):** `real`
- **Source:** `departments/communications/ACTION_ITEM_EXTRACTOR/main.py` (180 lines)

## Purpose

_No module docstring yet._

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

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
