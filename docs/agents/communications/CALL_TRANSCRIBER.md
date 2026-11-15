# CALL_TRANSCRIBER

- **Department:** `communications`
- **Status (static inventory):** `real`
- **Source:** `departments/communications/CALL_TRANSCRIBER/main.py` (179 lines)

## Purpose

Call transcriber: local speech-to-text of audio files with OpenAI Whisper or faster-whisper.
CallTranscriber.transcribe(filepath, language=None) returns {"filepath", "language", "text",
"segments"[, "language_probability", "duration_sec"]} where segments carry start, end and text. It
needs an authenticated caller (check_caller, traced) and reads only audio files (.wav, .mp3, .m4a, .flac,
.ogg, .webm) under this agent's data folder, CALL_RECORDER's recordings folder or config["audio_roots"].
transcribe_and_save(filepath, output_path=None, language=None) also writes the result as JSON
(default <audio>_transcript.json) and adds "transcript_path"; the output must be a .json path, not a
symlink, next to the audio file or under this agent's data folder (agent_dir). transcribe_to_text
returns just the text and raises RuntimeError on any error. health_check() reports whether the Whisper package imports
(status "ok" or "degraded"). The model is loaded lazily on first use; no audio leaves the machine.
State: no persistent state apart from the transcript files it is asked to write.
Failure: no caller returns {"error": "unauthenticated", ...}; a path that is not an audio file or lies
outside those folders returns {"error": <reason>}; a missing file returns {"error": "file_not_found:
<name>"}; any transcription error, including
the Whisper package not being installed, returns {"error": ...} instead of raising; a rejected output
path returns {"error": <reason>}.

## Class `CallTranscriber`

Local speech-to-text transcription using OpenAI Whisper (runs entirely on-device).
Requires: pip install openai-whisper  (or faster-whisper for speed)
Model sizes: tiny/base/small/medium/large — default 'small' balances speed+accuracy.
No audio is sent to any external API. Fully air-gapped capable.

- `__init__(config)`
- `health_check()`
- `transcribe(filepath, language)` — Transcribe a WAV/MP3/M4A file. Returns full text + segments with timestamps.
- `transcribe_and_save(filepath, output_path, language)` — Transcribe and save result as JSON alongside the audio file.
- `transcribe_to_text(filepath, language)` — Convenience: returns just the text string. Raises RuntimeError on failure: an error message is not a transcript.

## Depends on

- `velaris.core.access`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MEETING_SUMMARIZER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_kan93_agents.py`, `velaris/tests/test_requirements.py`
