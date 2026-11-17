# MEETING_SUMMARIZER

- **Department:** `communications`
- **Status (static inventory):** `real`
- **Source:** `departments/communications/MEETING_SUMMARIZER/main.py` (221 lines)

## Purpose

Meeting summarizer: builds a rule-based summary, decisions and action items from a transcript and stores them.

summarize(transcript, meeting_meta) takes a dict with "text" and "segments" (each segment has "text") and optional meta
(call_id, title, participants, recorded_at, transcript_path). It returns the summary (the five highest keyword-scoring
sentences in original order), decisions and action_items_raw (segments matching fixed regex phrase lists), word and
segment counts. With config["llm"] (an LLM) or summarize(use_llm=True) the summary is written by the model through the router at
sensitivity "restricted" (a meeting is personal data: never a free/community provider); the extractive summary stays in
"extractive_summary" and a failed model call keeps it as the summary ("llm_status" says what happened). summarize_from_file(path, meta) loads
a transcript JSON file first; a missing or invalid file raises OSError or ValueError. get_recent_meetings(limit) and
get_meeting(id) read back rows; an unknown id returns {"error": "not_found"}.
State: sqlite at <VELARIS_DATA>/agents/MEETING_SUMMARIZER/meetings.db, one row per summarize() call.

## Class `MeetingSummarizer`

Produces structured meeting summaries from transcripts.
Works purely rule-based (no LLM required), extracting:
- Decisions (sentences signalling agreement/finalization)
- Action items (sentences signalling tasks/deadlines)
- Extractive summary (top-scored sentences)
Optional: pass an LLM callable for richer summaries.

- `__init__(config)`
- `health_check()`
- `summarize(transcript, meeting_meta, use_llm)` — transcript: output from CALL_TRANSCRIBER (has 'text' + 'segments')
- `summarize_from_file(transcript_path, meeting_meta)` — Load a transcript JSON file and summarize it.
- `get_recent_meetings(limit)`
- `get_meeting(meeting_id)`

## Depends on

- `velaris.agentkit`
- `velaris.core.sqlite_util`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan93_rest.py`, `velaris/tests/test_no_state_in_source_tree.py`
