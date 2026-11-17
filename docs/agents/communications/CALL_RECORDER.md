# CALL_RECORDER

- **Department:** `communications`
- **Status (static inventory):** `real`
- **Source:** `departments/communications/CALL_RECORDER/main.py` (183 lines)

## Purpose

Call recorder: records microphone audio to local WAV files by running ffmpeg.

start(call_id, participants=None, meeting_title="", consent=False) launches ffmpeg (avfoundation
on macOS, dshow on Windows, alsa elsewhere; 16 kHz mono) and returns the session info. It needs an
authenticated caller (check_caller, traced) and consent that is exactly True; otherwise it records
nothing and returns {"error": "unauthenticated" / "denied" / "consent_required"}, or
{"error": "invalid_call_id"} for an empty call id. stop(session_id)
terminates it and returns filepath, size and duration (estimated from file size), or
{"error": "session_not_found"}. get_session(session_id) returns the public session fields
({} if unknown); list_recordings() lists the WAV files in the recordings directory;
health_check() reports status "degraded" when ffmpeg is missing or cannot be run; a missing
ffmpeg still raises when start is called.
State: sessions live in a module-level dict (lost on restart); audio goes to
config["recordings_dir"], default under the agent's VELARIS_DATA directory.

## Class `CallRecorder`

Local call/meeting audio recorder using system microphone.
Uses ffmpeg (must be installed) to capture audio to WAV files.
Output stored in config["recordings_dir"] (default: ./recordings/).
No audio leaves the machine — fully local.

- `__init__(config)`
- `health_check()`
- `start(call_id, participants, meeting_title, consent)` — Start recording. Returns session info including file path.
- `stop(session_id)` — Stop recording and return file path + duration info.
- `list_recordings()` — List all WAV files in recordings dir with basic metadata.
- `get_session(session_id)`

## Depends on

- `velaris.core.access`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CALL_TRANSCRIBER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_allowlist_departments.py`, `velaris/tests/test_kan93_agents.py`, `velaris/tests/test_no_state_in_source_tree.py`
