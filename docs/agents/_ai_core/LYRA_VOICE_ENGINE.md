# LYRA_VOICE_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/LYRA_VOICE_ENGINE/main.py` (243 lines)

## Purpose

Lyra voice engine: turns a spoken or typed command into a keyword-routed, simulated request and speaks the result.

LyraVoiceConfig.mode picks the input: "mock" (fixed fake transcript), "cli" (typed text) or anything else (microphone
via sounddevice, with whisper transcription when asr_backend is "whisper", else a typed fallback). Methods: listen()
(audio bytes or None), transcribe(audio), speak(text) (pyttsx3 or print; False only for empty text),
interpret_intent(text) (keyword match on infra/balance/status/simulate, otherwise "customer"; returns request_id, domain,
payload), run_once(user_text) and run_loop(handler, stop_after). run_once only names the engine it would route to and
returns a simulated {"status": "ok", ...}; it calls no other agent. A handler exception in run_loop becomes a failed reply.
Keeps no state. Missing audio packages are logged and the affected step returns None or an empty string.

## Class `LyraVoiceConfig`


## Class `LyraVoiceEngine`

- `__init__(cfg)`
- `listen()`
- `transcribe(audio_bytes)`
- `speak(text)`
- `interpret_intent(text)`
- `run_once(user_text)`
- `run_loop(handler, stop_after)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`
