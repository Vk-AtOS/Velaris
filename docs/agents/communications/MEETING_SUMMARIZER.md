# MEETING_SUMMARIZER

- **Department:** `communications`
- **Status (static inventory):** `real`
- **Source:** `departments/communications/MEETING_SUMMARIZER/main.py` (201 lines)

## Purpose

_No module docstring yet._

## Class `MeetingSummarizer`

Produces structured meeting summaries from transcripts.
Works purely rule-based (no LLM required), extracting:
- Decisions (sentences signalling agreement/finalization)
- Action items (sentences signalling tasks/deadlines)
- Extractive summary (top-scored sentences)
Optional: pass an LLM callable for richer summaries.

- `__init__(config)`
- `health_check()`
- `summarize(transcript, meeting_meta)` — transcript: output from CALL_TRANSCRIBER (has 'text' + 'segments')
- `summarize_from_file(transcript_path, meeting_meta)` — Load a transcript JSON file and summarize it.
- `get_recent_meetings(limit)`
- `get_meeting(meeting_id)`

## Depends on

- `velaris.core.sqlite_util`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_no_state_in_source_tree.py`
