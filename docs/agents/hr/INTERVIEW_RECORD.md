# INTERVIEW_RECORD

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/INTERVIEW_RECORD/main.py` (225 lines)

## Purpose

INTERVIEW_RECORD: a consent-gated, replayable record of an interview for a human reviewer.

Why it contains no AI-likelihood or cheating score, and what it records instead, is written out in velaris.agentkit.hiring_record (short
version: AI-text detectors flag 61.3% of non-native English writing, a proctoring product caught 0 of 6 cheaters, gaze error is 2 to 4.5
degrees; so none of those is computed). Staff methods here create the session, record interviewers' consent, hand out participant tokens,
register audio, run the optional local transcriber and mark events. The participant side (candidate_consent, ingest_event, ingest_audio,
candidate_withdraw in velaris.agentkit.hiring_record_gateway) works from tokens and is not in the identity-authenticated API: event
ingestion at browser speed cannot wait for an approval per event.

The evidence view and replay return personal data (a pad's text, transcripts), so they go through access.authorize_read("identity").
Erasure through ATS_CORE deletes events, audio files and transcripts and keeps only that a session existed.

## Class `InterviewRecord`

Consent-gated interview event record and evidence view. No judgement of any person is computed.

- `__init__(config)`
- `health_check()`
- `create_session(caller, application_id, interviewer_ids, retention_days)` — Open a record for one interview of an application. Participants: 'candidate' and the interviewers. Nothing is recorded until
- `give_consent(caller, session_id, scopes, notice_version)` — Your own consent to be recorded (scopes: events, audio, transcript). Only for yourself.
- `withdraw_my_consent(caller, session_id)`
- `issue_participant_token(caller, session_id, participant, hours)` — A token for a participant's browser (returned once, stored hashed, expiring). Works with the gateway functions.
- `register_audio_track(caller, session_id, participant, sha256, size_bytes, duration_s, mime)` — Reference an audio track that lives in the recorder's own store, by its SHA-256 (one per participant; consent for audio needed).
- `transcribe_track(caller, session_id, participant)` — Fill the transcript with the local transcriber hook, or report not_configured (the field stays empty). Needs transcript consent.
- `close_session(caller, session_id)` — Close the session. The ledger gets the chain head hash and counts, never content.
- `mark_event(caller, session_id, seq, mark, reason)` — A named reviewer marks an event 'relevant' or 'explained', with a reason. The mark is a ledger entry; it changes nothing else.
- `purge_expired_sessions(caller)` — Erase every session of the organisation past its retention_until date: events, audio, transcripts, consents (HR admins).
- `list_sessions(caller, application_id)` — Sessions with counts only: no content, no names.
- `evidence_view(caller, session_id)` — For a human reviewer: consent, the time-ordered events, pad edit summary, audio tracks by hash, transcript status and the
- `replay_pad(caller, session_id, pad_id, upto_seq)` — The shared pad's text as it stood after event `upto_seq` (0 = the end), rebuilt from the operation log.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.hiring_common`
- `velaris.agentkit.results`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/agentkit/hiring_common.py`, `velaris/agentkit/hiring_record.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_api_public.py`, `velaris/tests/test_hiring_api.py`, `velaris/tests/test_hiring_record.py`, `velaris/tests/test_hr_data_interview_retention.py`
