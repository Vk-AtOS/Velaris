# CALL_TRANSCRIBER

- **Department:** `communications`
- **Status (static inventory):** `real`
- **Source:** `departments/communications/CALL_TRANSCRIBER/main.py` (141 lines)

## Purpose

_No module docstring yet._

## Class `CallTranscriber`

Local speech-to-text transcription using OpenAI Whisper (runs entirely on-device).
Requires: pip install openai-whisper  (or faster-whisper for speed)
Model sizes: tiny/base/small/medium/large — default 'small' balances speed+accuracy.
No audio is sent to any external API. Fully air-gapped capable.

- `__init__(config)`
- `health_check()`
- `transcribe(filepath, language)` — Transcribe a WAV/MP3/M4A file. Returns full text + segments with timestamps.
- `transcribe_and_save(filepath, output_path, language)` — Transcribe and save result as JSON alongside the audio file.
- `transcribe_to_text(filepath, language)` — Convenience: returns just the text string.

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `MEETING_SUMMARIZER`
- **platform modules:** none found
- **tests:** `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_requirements.py`
