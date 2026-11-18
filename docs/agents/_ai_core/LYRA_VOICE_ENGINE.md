# LYRA_VOICE_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/LYRA_VOICE_ENGINE/main.py` (269 lines)

## Purpose

Lyra voice engine: turns a spoken or typed command into a keyword-routed, simulated request and speaks the result.

LyraVoiceConfig.mode picks the input: "mock" (fixed fake transcript), "cli" (typed text) or anything else (microphone
via sounddevice, with whisper transcription when asr_backend is "whisper", else a typed fallback). Methods: listen()
(audio bytes or None), transcribe(audio), speak(text) (pyttsx3 or print; False only for empty text),
interpret_intent(text) (keyword match on infra/balance/status/simulate, otherwise "customer"; returns request_id, domain,
payload), run_once(user_text) and run_loop(handler, stop_after, max_idle). run_once only names the engine it would route to and
returns a simulated {"status": "ok", ...}; it calls no other agent. In live (microphone) mode a transcript is acted on
only when it starts with the wake word (default "lyra"; the word is removed first); other speech is ignored, and with
no wake word configured (None) everything is acted on. run_loop hands the handler the same result dict in every mode,
counts a handled command (not an ignored one) toward stop_after, stops by itself after `max_idle` (default 120)
consecutive empty or ignored turns or when typed input ends (EOF), and stop() ends it from another thread. A handler
exception in run_loop becomes a failed reply.
Keeps no state. Missing audio packages are logged and the affected step returns None or an empty string.

## Class `LyraVoiceConfig`


## Class `LyraVoiceEngine`

- `__init__(cfg)`
- `listen()`
- `transcribe(audio_bytes)`
- `speak(text)`
- `interpret_intent(text)`
- `stop()`
- `run_once(user_text)`
- `run_loop(handler, stop_after, max_idle)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_c.py`, `velaris/tests/test_r3_voice_sim_lang.py`
