# CALL_RECORDER

- **Department:** `communications`
- **Status (static inventory):** `real`
- **Source:** `departments/communications/CALL_RECORDER/main.py` (155 lines)

## Purpose

_No module docstring yet._

## Class `CallRecorder`

Local call/meeting audio recorder using system microphone.
Uses ffmpeg (must be installed) to capture audio to WAV files.
Output stored in config["recordings_dir"] (default: ./recordings/).
No audio leaves the machine — fully local.

- `__init__(config)`
- `health_check()`
- `start(call_id, participants, meeting_title)` — Start recording. Returns session info including file path.
- `stop(session_id)` — Stop recording and return file path + duration info.
- `list_recordings()` — List all WAV files in recordings dir with basic metadata.
- `get_session(session_id)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_no_state_in_source_tree.py`
