# Research slice 02: interviewing candidates and telling genuine work from AI-assisted work

Researched 2026-11-11. All repository facts (licence, last push, stars, archived flag) were fetched that day from the GitHub API; model-weight licences were fetched from the model hub API. Anything not fetched is listed in section 4. No code from any project is reproduced here. GPL/AGPL/source-available projects were studied from README and public documentation only.

House rules assumed throughout: models propose, deterministic code decides; every action goes to the hash-linked ledger; a model never rejects or hires anyone, it only produces evidence for a named human.

---

## 1. Verification table

"Study" = permissive, worth reading for mechanism. "Docs only" = copyleft or restricted, architecture-level study only. "Skip" = not useful to us. "Avoid" = licence or status makes it a trap.

### 1.1 The named candidates

| Repo | Licence as fetched | Last push | Stars | Status | Verdict |
|---|---|---|---|---|---|
| jitsi/jitsi-meet | Apache-2.0 | 2026-11-11 | 30,221 | active | Study (architecture). Too heavy to run on one machine alongside everything else; recording needs Jibri. |
| livekit/livekit | Apache-2.0 | 2026-11-11 | 22,148 | active | Study. Best reference SFU; single Go binary. |
| livekit/agents | Apache-2.0 | 2026-11-11 | 15,178 | active | Study. Note: its end-of-turn model weights are under a separate "LiveKit Model License" (not permissive); the plugin code is Apache-2.0. |
| SYSTRAN/faster-whisper | MIT (code); converted large-v3 weights MIT on the hub; original Whisper large-v3 Apache-2.0, turbo MIT | 2026-11-10 | 26,668 | active | Study and use as a dependency. |
| pyannote/pyannote-audio | MIT (code). Weights differ: `speaker-diarization-community-1` is CC-BY-4.0 and gated (must accept conditions, needs a hub token); legacy `speaker-diarization-3.1` and `segmentation-3.0` are MIT and gated; the embedding model `wespeaker-voxceleb-resnet34-LM` is CC-BY-4.0. | 2026-11-09 | 10,782 | active | Study. Usable, with attribution and a one-time gated download. README now pushes a paid hosted tier; the library also has opt-out telemetry. |
| engineer-man/piston | MIT | 2026-07-31 | 2,842 | active, slow | Study. Correction: it is a thin MIT job runner around the `isolate` binary (GPL-2.0-or-later), run in a privileged container. Public API is no longer free (README, since 2026-02-15). |
| judge0/judge0 | GPL-3.0 | 2026-10-26 | 4,516 | active | Docs only. Do not read source. |
| calcom/cal.com | **Path now redirects to calcom/cal.diy, MIT** | 2026-11-11 | 49,935 | active | Study, with caveats (below). |

### 1.2 Corrections to the candidate list

1. **calcom/cal.com is no longer the open repository.** The path resolves to `calcom/cal.diy`. Its README describes it as the community edition with all enterprise code removed, "100% MIT-licensed", and "strictly recommended for personal, non-production use". Teams, Organizations, Insights, Workflows (which is where reminders lived) and SSO are stated as removed. The LICENSE file is plain MIT, copyright Cal.com, Inc. So the licence is better than memory suggested (it used to be AGPL plus a commercial folder), but the feature set is smaller.
2. **piston is not itself a sandbox.** Its `job.js` shells out to `isolate` for box init and run. The MIT licence covers the wrapper only.
3. **pyannote "MIT" is true only for code.** The current recommended pipeline's weights are CC-BY-4.0 and gated.
4. **rhasspy/piper (TTS) is archived** (last push 2025-08-26, MIT). Its successor `OHF-Voice/piper1-gpl` is GPL-3.0. Do not assume Piper is permissive any more.
5. **NVIDIA/NeMo** now resolves to `NVIDIA-NeMo/Speech` (Apache-2.0). **e2b-dev/infra** resolves to `e2b-dev/runtime`. **daytonaio/daytona** is archived with no licence detected.
6. **codemirror/dev, codemirror/view, codemirror/state** show as archived on GitHub (pushed 2026-04-15). Where development moved was not checked.

### 1.3 Additional repositories checked

| Repo | Licence as fetched | Last push | Stars | Status | Verdict |
|---|---|---|---|---|---|
| **Rooms / media** | | | | | |
| aiortc/aiortc | BSD-3-Clause | 2026-11-07 | 5,127 | active | Study. WebRTC in Python; the shortest path for us. |
| pion/webrtc | MIT | 2026-11-10 | 16,894 | active | Study (reference Go implementation). |
| pion/turn | MIT | 2026-11-11 | 2,279 | active | Study. |
| coturn/coturn | BSD-style (custom text) | 2026-11-10 | 14,554 | active | Use as TURN relay if needed. |
| livekit/egress | Apache-2.0 | 2026-11-11 | 373 | active | Study (recording design). |
| jitsi/jibri | Apache-2.0 | 2026-11-09 | 673 | active | Study as a cautionary design. |
| jitsi/jitsi-videobridge | Apache-2.0 | 2026-11-11 | 3,109 | active | Skip. |
| versatica/mediasoup | ISC | 2026-11-11 | 7,417 | active | Skip (library, Node/C++). |
| bluenviron/mediamtx | MIT | 2026-11-11 | 20,665 | active | Skip for now. |
| jech/galene | MIT | 2026-11-09 | 1,430 | active | Study if a small SFU is wanted. |
| OpenVidu/openvidu | Apache-2.0 | 2026-11-11 | 2,144 | active | Skip (wraps LiveKit). |
| meetecho/janus-gateway | GPL-3.0 | 2026-11-10 | 9,205 | active | Docs only. |
| bigbluebutton/bigbluebutton | LGPL-3.0 | 2026-11-11 | 9,275 | active | Docs only. |
| element-hq/element-call | AGPL-3.0 | 2026-11-11 | 1,024 | active | Docs only. |
| miroslavpejic85/mirotalk | AGPL-3.0 | 2026-11-11 | 4,839 | active | Docs only. |
| **Voice agents** | | | | | |
| pipecat-ai/pipecat | BSD-2-Clause | 2026-11-11 | 17,200 | active | Study. Best reference for the voice loop. |
| pipecat-ai/smart-turn | BSD-2-Clause (code and weights) | 2026-11-09 | 1,663 | active | Study and use. Hindi, Marathi, Bengali listed among 23 languages. |
| pipecat-ai/pipecat-flows | BSD-2-Clause | 2026-07-05 | 626 | ARCHIVED | Skip (a `flows` package now sits inside pipecat). |
| kyutai-labs/unmute | MIT (code); Kyutai STT/TTS weights CC-BY-4.0 | 2026-09-09 | 1,547 | active | Study only. README requires an x86_64 CUDA GPU with 16 GB VRAM; no aarch64. |
| kyutai-labs/moshi | Apache-2.0 | 2026-09-09 | 11,488 | active | Skip (speech-to-speech; hard to audit turn by turn). |
| huggingface/speech-to-speech | Apache-2.0 | 2026-11-11 | 13,678 | active | Study. |
| gradio-app/fastrtc | MIT | 2026-10-21 | 4,636 | active | Study. |
| bolna-ai/bolna | MIT | 2026-11-11 | 821 | active | Skip (telephony focus). |
| fixie-ai/ultravox | MIT | 2025-12-12 | 4,587 | stale | Skip. |
| vocodedev/vocode-core | MIT | 2024-11-15 | 3,808 | dead | Skip. |
| TEN-framework/ten-framework | Apache-2.0 **with additional conditions** (no hosting on end-user devices; non-compete clause) | 2026-11-11 | 11,230 | active | Avoid. |
| FoloUp/FoloUp | MIT | 2026-10-17 | 1,281 | active | Study as the only notable open AI-interviewer. It is a web front end over hosted voice, LLM, auth and database services, so it is not local-first. |
| **ASR / diarisation / VAD / TTS** | | | | | |
| openai/whisper | MIT | 2026-08-31 | 112,457 | slow | Reference. |
| ggml-org/whisper.cpp | MIT | 2026-11-10 | 55,098 | active | Use on Apple Silicon. |
| m-bain/whisperX | BSD-2-Clause | 2026-10-22 | 25,215 | active | Study (word alignment plus speaker assignment). |
| QuentinFuxa/WhisperLiveKit | Apache-2.0 | 2026-11-08 | 11,238 | active | Study (streaming policies). |
| ufal/whisper_streaming | MIT | 2025-11-12 | 3,680 | superseded | Study the LocalAgreement idea. |
| ufal/SimulStreaming | MIT | 2026-07-12 | 697 | active | Study. |
| collabora/WhisperLive | MIT | 2026-11-11 | 4,354 | active | Skip. |
| snakers4/silero-vad | MIT | 2026-10-22 | 10,638 | active | Use. |
| k2-fsa/sherpa-onnx | Apache-2.0 | 2026-11-11 | 15,884 | active | Study and likely use: ASR, VAD, diarisation, TTS on ONNX without a deep-learning framework. |
| NVIDIA-NeMo/Speech | Apache-2.0 (code); Parakeet TDT 0.6b v3, Canary 1b v2, streaming Sortformer v2 are CC-BY-4.0; Sortformer v2.1 and the streaming Nemotron ASR are under the NVIDIA Open Model License | 2026-11-11 | 18,734 | active | Study. Check each checkpoint's licence. |
| juanmc2005/diart | MIT | 2026-06-19 | 2,048 | slowing | Study the idea; WhisperLiveKit now marks its diart profile "not recommended". |
| modelscope/FunASR | MIT (code); SenseVoice weights under a custom model licence | 2026-11-11 | 20,998 | active | Skip. |
| modelscope/3D-Speaker | Apache-2.0 | 2025-12-08 | 3,214 | slow | Skip. |
| wenet-e2e/wespeaker | Apache-2.0 | 2026-09-22 | 1,463 | active | Study (speaker embeddings). |
| speechbrain/speechbrain | Apache-2.0 | 2026-10-14 | 11,933 | active | Study (ECAPA embeddings, Apache-2.0 weights). |
| OpenMOSS/MOSS-Transcribe-Diarize | Apache-2.0 | 2026-10-21 | 2,272 | active | Watch (joint transcription and diarisation in one 0.9B model). Not evaluated here. |
| moonshine-ai/moonshine | MIT code; models MIT except legacy non-English non-streaming models (non-commercial) | 2026-11-10 | 11,474 | active | Study (small streaming ASR). |
| AI4Bharat/IndicConformerASR | MIT; hub weights `indic-conformer-600m-multilingual` MIT, gated | 2025-06-20 (repo), weights updated 2026-10-08 | 107 | slow | Use for Indian languages; test first. |
| hexgrad/kokoro | Apache-2.0 (code and 82M weights) | 2025-08-06 | 10,054 | stale but usable | Use for English TTS. |
| resemble-ai/chatterbox | MIT (code and weights) | 2026-11-04 | 27,760 | active | Study. |
| kyutai-labs/pocket-tts | MIT code; weights CC-BY-4.0 gated | 2026-11-10 | 10,263 | active | Study (CPU TTS). |
| huggingface/parler-tts | Apache-2.0; `ai4bharat/indic-parler-tts` weights Apache-2.0, gated | 2024-12-10 | 5,600 | stale | Use the Indic weights if Indian-language speech out is needed. |
| coqui-ai/TTS | MPL-2.0; XTTS-v2 weights under a non-commercial model licence | 2024-08-16 | 46,214 | dead | Avoid. |
| OHF-Voice/piper1-gpl | GPL-3.0 | 2026-11-09 | 6,248 | active | Docs only. |
| **Sandboxes** | | | | | |
| ioi/isolate | GPL-2.0-or-later (licence text read) | 2026-10-26 | 1,503 | active | Docs only. Calling the binary as a separate process is the normal way to use it. |
| google/nsjail | Apache-2.0 | 2026-11-10 | 4,188 | active | Study and use on Linux. |
| google/gvisor | Apache-2.0 | 2026-11-11 | 19,964 | active | Use as a container runtime on Linux. |
| criyle/go-judge | MIT | 2026-11-05 | 638 | active | Study. Cleanest permissive judge. |
| firecracker-microvm/firecracker | Apache-2.0 | 2026-11-10 | 37,969 | active | Skip for now (needs KVM). |
| superradcompany/microsandbox | Apache-2.0 | 2026-11-11 | 9,027 | active | Watch. |
| e2b-dev/E2B, e2b-dev/runtime | Apache-2.0 | 2026-11-11 | 14,809 / 1,835 | active | Skip (cloud-shaped). |
| langgenius/dify-sandbox | Apache-2.0 | 2026-11-10 | 1,281 | active | Study (seccomp allow-list approach). |
| vndee/llm-sandbox | MIT | 2026-11-06 | 1,144 | active | Skip. |
| hyperlight-dev/hyperlight | Apache-2.0 | 2026-11-11 | 4,798 | active | Skip. |
| bytecodealliance/wasmtime | Apache-2.0 | 2026-11-11 | 18,848 | active | Study. |
| pyodide/pyodide | MPL-2.0 | 2026-11-11 | 14,934 | active | Use unmodified (file-level copyleft only applies if we modify its files). |
| containers/bubblewrap | LGPL-2.x (text read) | 2026-10-14 | 9,455 | active | Use as a binary. |
| DMOJ/judge-server | AGPL-3.0 | 2026-10-12 | 981 | active | Docs only. |
| windmill-labs/windmill | Mixed Apache-2.0 / AGPL-3.0 | 2026-11-11 | 18,528 | active | Docs only. |
| **Process capture / editors** | | | | | |
| rrweb-io/rrweb | MIT | 2026-11-11 | 20,365 | active | Study (event-sourced session recording). |
| yjs/yjs | MIT | 2026-11-09 | 23,050 | active | Study (edit history as an update log). |
| microsoft/monaco-editor | MIT | 2026-11-11 | 46,965 | active | Use. |
| openreplay/openreplay | Multiple licences | 2026-11-11 | 13,135 | active | Skip. |
| **Proctoring / gaze / detectors** | | | | | |
| SafeExamBrowser/seb-win-refactoring | MPL-2.0 | 2026-11-11 | 369 | active | Skip (lockdown browser; requires install, Windows). |
| openedx/edx-proctoring | AGPL-3.0 | 2026-11-10 | 69 | active | Docs only (an integration layer for vendors). |
| lebmatter/exampro | MIT | 2026-08-19 | 72 | small | Skip. |
| Hobby proctoring repos (several, 30 to 280 stars) | mostly no licence | mixed | | | Avoid. None publishes measured error rates. |
| google-ai-edge/mediapipe | Apache-2.0 | 2026-11-11 | 37,644 | active | Use for in-browser face count. |
| brownhci/WebGazer | GPL-3.0-or-later style text | 2026-02-24 | 3,921 | slow | Docs only. |
| antoinelame/GazeTracking | MIT | 2026-04-27 | 2,652 | slow | Skip. |
| liamdugan/raid | MIT | 2026-11-10 | 226 | active | Study (benchmark, not a tool to deploy). |
| ahans30/Binoculars | BSD-3-Clause | 2024-05-14 | 434 | stale | Study only. |
| baoguangsheng/fast-detect-gpt | MIT | 2026-02-07 | 439 | slow | Study only. |
| eric-mitchell/detect-gpt | MIT | 2023-03-04 | 479 | dead | Skip. |
| **Scheduling** | | | | | |
| collective/icalendar | BSD-2-Clause | 2026-11-11 | 1,187 | active | Use. |
| python-caldav/caldav | Apache-2.0 (as reported by the API) | 2026-11-11 | 413 | active | Use if CalDAV free/busy is wanted. |
| dateutil/dateutil | Apache-2.0 / BSD (dual, text read) | 2026-11-01 | 2,646 | active | Use (`rrule`), or stdlib `zoneinfo` alone. |
| allenporter/ical | Apache-2.0 | 2026-11-11 | 50 | active | Alternative. |
| alextselegidis/easyappointments | GPL-3.0 | 2026-11-02 | 4,491 | active | Docs only. |
| lukevella/rallly | AGPL-3.0 | 2026-11-11 | 5,357 | active | Docs only. |
| nateherkai/snagtime | MIT | 2026-08-28 | 414 | small | Skip. |
| **Scoring statistics** | | | | | |
| statsmodels/statsmodels | BSD-3-Clause | 2026-11-11 | 11,748 | active | Use (Cohen's and Fleiss' kappa). |
| raphaelvallat/pingouin | GPL-3.0 | 2026-10-24 | 1,946 | active | Avoid as a dependency; write ICC ourselves. |
| pln-fing-udelar/fast-krippendorff | GPL-3.0 | 2026-10-15 | 162 | active | Avoid; Krippendorff's alpha is a published formula, write it ourselves. |

---

## 2. Sub-areas

### 2a. Video interview rooms and recording

**How the best ones work.** A WebRTC room has three parts: signalling (who is in the room, exchange of session descriptions and network candidates), NAT traversal (STUN to discover addresses, TURN to relay when direct paths fail), and media routing. Jitsi and LiveKit both use a selective forwarding unit: each participant sends one upstream and the server forwards packets to the others without decoding, choosing which simulcast layer each receiver gets. LiveKit is a single Go binary built on pion; Jitsi is several services (web, signalling, bridge, recorder).

Recording is where they differ and where the lesson is. Jibri's README states that it launches a Chrome instance in a virtual framebuffer and captures the screen with ffmpeg, and that one Jibri handles one recording at a time. LiveKit egress offers that same style (room composite: Chrome plus a web template, transcoded with GStreamer) but also **track egress**, which uses the server SDK to write each participant's track to its own file with no browser.

**What makes them good.** Simulcast and congestion control for bad networks; per-track recording that costs almost no CPU; token-based room admission.

**What they get wrong for us.** Screen-capture recording needs a browser and an encoder per interview, which does not fit one machine that is also running speech models. Composite recording also throws away the most useful property for integrity work: who said what on which channel. And for a two- or three-person interview an SFU is more machinery than the problem needs.

**Minimum original design (about 500 lines Python, 250 lines browser script).** One FastAPI WebSocket endpoint for signalling, admission by a signed single-use room token. The server joins every room as a WebRTC peer using `aiortc` (BSD-3-Clause), so every participant has one connection to the server. The server writes each inbound audio and video track to its own file as received, stamps each file with start offset and participant identity, and (when a human interviewer is present) relays tracks between participants. A hash of each finished file goes into the ledger together with consent state. Playback composes tracks offline with ffmpeg only if someone asks for a single file. A TURN relay (coturn or pion/turn) is added only when a candidate cannot connect directly. Consent is a deterministic gate: no track is written until the candidate has explicitly accepted recording, and the acceptance is a ledger entry.

ponytail: one Python process relays media, fine for 2 to 4 participants per room and a handful of rooms; move to a LiveKit server (Apache-2.0) with track egress when concurrent rooms matter.

**Beyond them.** Per-speaker channels from the start, so diarisation of known participants is free and "an extra voice on the candidate's channel" becomes a clean question. Recording hashes in the ledger give tamper evidence that none of these projects offer.

### 2b. Voice AI interviewer

**How the best ones work.** pipecat (BSD-2-Clause, source read) models the conversation as typed frames flowing through a chain of processors: transport in, voice activity detection, speech-to-text, context aggregation, language model, text-to-speech, transport out. Control frames (user started speaking, user stopped, interruption) travel on the same path so any stage can cancel work in flight.

Turn-taking is the key algorithm, and both pipecat and LiveKit Agents now treat it as pluggable strategies rather than one silence timer:

- Voice activity detection (Silero) marks speech and silence. pipecat's defaults are confidence 0.7, 0.2 s to confirm start, 0.2 s to confirm stop.
- At each silence, an end-of-turn model decides "finished" or "still thinking". pipecat's Smart Turn v3 is an audio-native classifier on a Whisper-tiny encoder (about 8M parameters, 8 MB quantised), takes up to 8 s of the current turn, and per its README runs in roughly 10 to 100 ms on CPU. It is run only when the VAD reports silence, and re-run on the whole turn if speech resumes. LiveKit's detector is text-based on the running transcript; its weights are not permissively licensed.
- A fallback timer ends the turn anyway. LiveKit's defaults: minimum endpointing delay 0.5 s, maximum 3.0 s.
- The turn is closed only when the detector says complete and a final transcript has arrived (pipecat waits for the transcript, bounded by the recogniser's reported tail latency).
- Interruption: if the user speaks while the agent is speaking, downstream audio is cancelled and the conversation context is truncated to what was actually spoken. LiveKit requires 0.5 s of speech to count as an interruption and, if nothing meaningful follows within 2.0 s, classifies it as a false interruption and resumes the agent's speech.
- Speculation: pipecat can start generating a reply on a provisional end-of-turn and hold the output behind a gate until the turn is confirmed, discarding it if the user carries on.

**Latency budget.** From the defaults above, the unavoidable wait before the model even starts is VAD stop (0.2 s) plus turn model (under 0.1 s) plus final transcript. My estimate for a fully local cascade on one machine is 1.0 to 1.8 s to first audio (recogniser tail 0.2 to 0.4 s, local model first token 0.3 to 0.8 s, speech synthesis first chunk 0.1 to 0.3 s). This estimate was not measured.

**What makes them good.** Turn-taking separated from the model; cancellation as a first-class frame; context that reflects what was really said; sentence-level streaming into speech synthesis.

**What they get wrong for an interview.** They are tuned for customer-service speed. A candidate who pauses for four seconds to think is behaving well, and a 3 s cap will cut them off. General end-of-turn models are weak on Indian languages: a 2026 paper on Tamil telephone speech reports Smart Turn v3 at 70.3% zero-shot accuracy, rising to 86.1% after fine-tuning. The frameworks have no concept of a question plan, a time budget, or an auditable reason for each follow-up. And the one open AI-interviewer project (FoloUp) asks the model for an overall 0 to 100 score and a soft-skills summary directly, which is exactly what our rules forbid.

**Minimum original design (about 700 lines).** A deterministic interview state machine owns the session: an ordered list of rubric questions, each with a maximum number of follow-ups, a time cap, and the competencies it is meant to evidence. The model is called for two narrow jobs only: (1) propose one follow-up question given the question, the rubric anchors and the candidate's last answer, returning structured output with the quoted span it is probing; (2) nothing else during the interview. Code decides whether to ask the follow-up (budget left, time left, the quoted span really appears in the transcript) or move on. The audio loop is a small asyncio pipeline: Silero VAD, an end-of-turn check (Smart Turn weights are BSD-2-Clause) with interview-specific timing (long maximum wait, and a spoken "take your time" rather than a cut-off), faster-whisper or whisper.cpp for recognition, Kokoro for English speech out, barge-in by cancelling playback. Every question asked, every follow-up proposal (accepted or declined, with reason) and every turn boundary is a ledger event. The candidate is told at the start that the interviewer is automated and that a named person reviews the result.

ponytail: one fixed English voice and half-duplex turn-taking with barge-in; add Indian-language recognition (IndicConformer, MIT, gated) and speech (Indic Parler-TTS, Apache-2.0, gated) when a role needs it.

**Beyond them.** Follow-ups that must cite the candidate's own words (see 2e); a plan that guarantees every candidate for a role gets the same core questions, which is what makes later scoring comparable; a full audit trail of why each question was asked.

### 2c. Transcription and speaker diarisation, second-voice detection

**How the best ones work.**

- *faster-whisper* (MIT) re-implements Whisper inference on an optimised inference engine with quantisation, adds Silero VAD filtering to skip silence (which also suppresses Whisper's habit of inventing text over silence), batched decoding, and word timestamps derived from cross-attention alignment.
- *WhisperX* (BSD-2-Clause) cuts audio at VAD boundaries, transcribes in batches, then force-aligns words with a separate phoneme model for tighter word times, then assigns each word to a speaker from a diarisation pass.
- *Streaming*: Whisper is not a streaming model. WhisperLiveKit's README names the two policies that make it usable live: LocalAgreement (re-transcribe a growing buffer and commit only the prefix on which consecutive passes agree) and the newer AlignAtt policy (stop emitting when attention reaches the end of the available audio).
- *pyannote* runs a neural segmentation model over short sliding windows to get local speaker activity including overlap, extracts a speaker embedding per local speaker, and clusters embeddings across the file to get global identities. Its README reports diarisation error for the open `community-1` pipeline of 11.2% (VoxConverse), 17.0% (AMI headset), 20.2% (DIHARD 3), 26.7% (CALLHOME) and 44.6% (AVA-AVD), and 31 to 37 s of compute per hour of audio on a data-centre GPU.
- *Streaming Sortformer* (NVIDIA) is an end-to-end model that outputs speaker activity for up to four speakers directly.
- *sherpa-onnx* (Apache-2.0) packages VAD, recognition and diarisation on ONNX runtime with no deep-learning framework, which suits one machine.

**What they get wrong.** A 10 to 25% diarisation error on realistic audio means short spurious "extra speaker" segments are routine. Clustering has to guess the number of speakers. Whisper accuracy on Indian-accented English and on Hindi-English code-switching was not measured here and should not be assumed.

**Minimum original design (about 350 lines).** Because 2a records one track per participant, we do not diarise the conversation at all: speaker identity is the channel. Transcribe each channel with faster-whisper with VAD and word timestamps, merge by time, store transcript segments with channel, start, end and confidence. Second-voice detection then asks one narrow question of the candidate's channel only:

1. Mask every interval in which another participant's channel (or the AI interviewer's output) was active, plus a short tail. This removes the single largest false positive: the interviewer's voice leaking from the candidate's loudspeaker into their microphone.
2. On the remaining speech, compute speaker embeddings per segment (ECAPA from speechbrain, Apache-2.0 code and weights, or a WeSpeaker model) and compare each to the candidate's enrolment embedding taken from their first answers.
3. Report intervals where speech is present, the embedding is far from the candidate's, and the total exceeds a duration floor.

The output is a list of time ranges with playable clips, shown to a human as "speech on the candidate's microphone that does not match the candidate's voice; listen". It is never a score and never a flag on the candidate's record without a human confirming it.

**Beyond them.** Echo masking using the known far-end signal, and enrolment-based verification instead of blind clustering, both possible only because we own the recording design.

### 2d. Coding and work-sample assessment

**How the best ones work.**

- *piston* (MIT, source read) keeps a bounded pool of numbered sandbox boxes. For each job it initialises a box with the `isolate` binary, writes the submitted files under the box after checking that no file path escapes the submission directory, runs a compile stage and a run stage through `isolate` with control-group accounting, and reads back a metadata file with exit code, signal, CPU time, wall time and memory. Defaults in its config: networking disabled, 3 s run and 10 s compile limits (wall and CPU), 64 processes, 2,048 open files, 10 MB file size, 64 concurrent jobs, output buffer capped. It requires a privileged container and cgroup v2.
- *isolate* (GPL, README only) is the sandbox used by programming contests: Linux namespaces plus control groups plus resource limits.
- *judge0* (GPL-3.0, README and public advisories only) is an API, a queue and workers around `isolate`. In 2024 it had three published sandbox escapes (CVE-2024-28185, CVE-2024-28189, CVE-2024-29021). The advisory summaries describe the first two as the service writing a run script into, and running `chown` on, paths inside the sandbox directory that the submitted code could replace with symbolic links. The lesson is general: the sandbox primitive held; the privileged glue code that touched candidate-controlled files did not.
- *go-judge* (MIT) implements its own sandbox (namespaces, control groups, a default seccomp filter that reports "dangerous syscall"), keeps a pool of pre-created containers for speed, has an in-memory file store so compile output can feed several test runs, and returns a precise status vocabulary (time limit, memory limit, output limit, signalled, non-zero exit, internal error). Its README notes that when swap accounting is unavailable the memory limit is not fully enforceable and offers a fail-closed start-up flag.
- *nsjail* (Apache-2.0) is a single binary: namespaces, resource limits, control groups and seccomp policies written in a small policy language.
- *gVisor* (Apache-2.0) is a user-space kernel used as a container runtime; system calls from the workload never reach the host kernel directly. *Firecracker* gives a real virtual-machine boundary but needs KVM.
- *Pyodide* runs CPython compiled to WebAssembly in the candidate's own browser.

None of these capture process. The process-capture references are rrweb (MIT), which records a page as an initial snapshot plus a timestamped stream of mutations and input events that can be replayed, and Yjs (MIT), where a document is the sum of an append-only log of updates.

**What they get wrong.** They judge only the final submission. They assume Linux with privileged containers. Wall-clock limits are noisy on a loaded single machine, so timing-based test verdicts flap.

**Minimum original design (about 450 lines Python, 300 lines browser script).**

*Execution.* The stack already uses Docker, and on a Mac Docker runs inside a Linux virtual machine, which is a stronger boundary than namespaces alone. One container per run, created fresh and destroyed after: no network, read-only root file system, a small temporary file system for the working directory, non-root user, all capabilities dropped, no privilege escalation, process-count, memory and CPU limits, wall-clock kill from the host, output truncated at a byte cap. Candidate files are written into the container by streaming an archive to it, never by the host process touching a mounted directory as root (the judge0 lesson). Tests are deterministic and count-based where possible, not time-based. Results (per-test pass or fail, exit status, resource use, image digest) go to the ledger.

ponytail: container-per-run costs roughly a second of start-up; move to gVisor as the runtime or an nsjail pool on a Linux host when throughput matters. Optional instant feedback by running Python in the candidate's browser with Pyodide; that result is never trusted for scoring.

*Process capture.* The editor (Monaco, MIT) emits a stream of change events. We store each as: sequence number, milliseconds since start, range replaced, inserted text, and origin (typed, paste, drop, undo or redo, completion). Alongside: paste events with length and content hash, focus and visibility changes, every run with its result. The log is append-only, sent in small batches, and each batch is hash-chained into the ledger so it cannot be rewritten afterwards. From the log, deterministic code can rebuild the file at any instant and compute plain descriptive facts: share of final characters that arrived by paste, the largest single insertion, time to first keystroke, number of runs, number of deletions, longest idle gap. A reviewer gets a scrub-bar replay.

**Beyond them.** The work sample is judged on its history, not just its end state, and the interviewer (human or the 2b agent) then asks the candidate to change their own solution live ("make it handle an empty list", "why this data structure"). A person who wrote it can; a person who pasted it usually cannot. Work samples are among the strongest predictors in the selection literature (Sackett et al. 2022 list work samples, cognitive ability and structured interviews as the strongest), so this is where effort pays.

### 2e. Interview integrity

The honest summary: **automated cheating detection does not work well enough to act on, and the research says so plainly.** What does work is designing the interview so that outside help is less useful, and showing a human a small number of factual, replayable events.

**Evidence on proctoring signals.**

- A controlled experiment with a widely used commercial proctoring product (Bergmans et al., 2021, 30 computer-science students, 6 instructed to cheat) found that none of the cheaters was flagged by the software and only one was caught by a human reviewing the footage. The authors put the tool's sensitivity "very close to zero" and compare it to a placebo whose value is deterrence.
- A reverse-engineering study of four proctoring suites (Burgess et al., USENIX Security 2022) found all anti-cheating measures could be trivially bypassed and examined skin-tone effects in the face classifier.
- An analysis of about 357 students (Yoder-Himes et al., 2022) found students with the darkest skin tones were flagged for 7.64% of their exam time against 3.33% (medium) and 1.56% (lighter), with women with the darkest skin tones affected most. "Face not detected" is therefore a biased signal.
- Webcam gaze estimation has an error of roughly 2 to 4.5 degrees of visual angle: 4.17 degrees in the original WebGazer paper; a 2026 large-scale validation reports about 2.05 degrees for a newer tracker and markedly worse for WebGazer, degrading with head movement. That is too coarse to tell reading a script from looking at the video window, and no study was found validating "reading from screen" detection in interviews.

**Evidence on AI-text detection.**

- Liang et al. (2023): seven detectors misclassified TOEFL essays by non-native writers as AI-generated at an average false-positive rate of 61.3%; about 19% of the essays were flagged unanimously by all seven. US student essays were classified accurately. For an India-only product, almost every candidate writes English as an additional language. This is the worst-case population for these tools.
- The best-known vendor withdrew its own classifier in July 2023 for "low rate of accuracy": 26% true positives, 9% false positives on its own challenge set.
- Weber-Wulff et al. (2023) tested 14 tools: all scored below 80% accuracy, only 5 above 70%.
- RAID (ACL 2024; over 6 million generations, 11 models, 11 attacks, 12 detectors): detectors that claim 99% are "easily fooled" by attacks, sampling changes and unseen models.
- Paraphrasing: Krishna et al. (2023) dropped one detector from 70.3% to 4.6% detection at a fixed 1% false-positive rate; Sadasivan et al. (2023) show the same with recursive paraphrasing and also show human text can be made to look machine-written.
- Binoculars (2024) reports over 90% detection at a 0.01% false-positive rate on its own test sets. That is the strongest published zero-shot claim, but it was not validated on Indian-English writers and RAID-style attacks apply.

**Evidence on keystroke dynamics.** Kundu et al. (2024) report 74.98 to 85.72% accuracy when the writing condition is known and 52.24 to 80.54% when it is not. A 2025 extension (130 participants) finds keystroke models beat text-only detectors but have "limitations under more challenging adversarial conditions". A 2026 Vietnamese study finds plain transcription is reliably identified while paraphrasing and deliberately altered typing are "frequently misclassified as bona fide". So: retyping an answer verbatim leaves a trace; anything smarter does not, and accuracy near 52% in the general case is a coin toss.

**Evidence on humans spotting it.** In a preregistered experiment (Canagasuriam and Lukacik, 2024, N = 245, recorded video interviews), candidates using a chatbot received considerably higher content and overall scores, and delivery ratings did not differ between conditions. Raters cannot hear the difference. No controlled study of detection in live two-way interviews was found.

**Evidence that automated interviewing itself is viable.** A field experiment with 70,000 applicants (Jabarian and Henkel, 2025) randomly assigned interviews to human recruiters or a voice agent; agent-interviewed applicants were 12% more likely to receive offers and showed higher retention. Decisions were still made by people. This supports 2b; it says nothing about cheating.

**Interview designs that are hard to fake (reasoned, not measured; see section 4).**

1. *Follow-ups on the candidate's own words.* Each follow-up must quote a span from the last answer and ask for a specific detail of it: a number, a sequence, a trade-off, what went wrong. Generic model-written answers are thin on checkable specifics, and a relay through a second device adds delay on every turn.
2. *Resume consistency.* Extract dated, checkable claims from the resume (role, period, tool, scale). Ask about two or three of them in ways that require lived detail. Code compares stated facts across resume, screening answers and interview (dates, team size, tools) and lists mismatches with both sources quoted. A mismatch is a prompt for the human, not a verdict.
3. *Modify your own work.* After a work sample, ask for a live change to the candidate's submission (2d).
4. *Allow tools, grade reasoning.* For roles where AI tools are normal at work, say they are allowed in the work sample and score explanation, verification and judgement instead. This removes the incentive to hide.
5. *Tell candidates what is recorded.* Deterrence is the one effect the proctoring study did find.

**Minimum original design (about 400 lines).** A browser collector for focus, visibility, paste and full-screen events; an optional in-browser face count (MediaPipe, Apache-2.0) that reports only "more than one face" with a still frame and never reports absence; the second-voice check from 2c; the process log from 2d; the consistency checker above. All of it feeds one "integrity timeline" on the review screen: time-ordered factual events, each with its evidence (clip, frame, pasted text, quoted spans). There is no integrity score, no threshold, no colour coding, and no model-written judgement of honesty. Only a named reviewer can mark an event "relevant" or "explained", with a reason, and that marking is a ledger entry.

### 2f. Scheduling and invitations

**How the best one works.** cal.diy (MIT, source skimmed) computes availability as interval arithmetic. A host's weekly working hours are expanded into concrete date ranges in the schedule's time zone; out-of-office ranges are removed; busy intervals are gathered from existing bookings, from connected calendars' free/busy queries, and from booking limits (a daily or weekly cap is converted into synthetic busy blocks); buffers are added around busy intervals; the busy set is subtracted from the available set. The remaining ranges are cut into slots at a fixed frequency, skipping anything earlier than now plus a minimum notice, with slot starts aligned to sensible clock times. Its code comments note that alignment has to be checked in the local zone, not UTC, precisely because of half-hour offsets such as India's.

**What makes it good.** Everything reduces to subtracting interval sets; limits and buffers are expressed as busy time rather than special cases.

**What it gets wrong for us.** It is a very large TypeScript monorepo. The open edition has dropped teams, round-robin and workflows (reminders), which are exactly what a hiring panel needs, and its own README says it is not for production.

**The public standards give the pathway.** RFC 5545 (iCalendar event format), RFC 5546 (scheduling methods: request, reply, cancel; a reschedule is the same event identifier with an incremented sequence number), RFC 6047 (sending those by email), RFC 4791 (CalDAV, including a free/busy query), RFC 7953 (publishing availability).

**Minimum original design (about 400 lines).** Tables: interviewer working hours, time-off, bookings. All instants stored in UTC; display in Asia/Kolkata via the standard library (India has one zone and no daylight saving, which removes most of the hard cases, but storing UTC keeps the door open). Slot generation is the interval subtraction above for one interviewer, and an intersection across interviewers for a panel. Double-booking is prevented by a PostgreSQL exclusion constraint on interviewer and time range, not by application checks. Invitations are an email with a calendar attachment built with `icalendar` (BSD-2-Clause) using the request method; reschedule and cancel reuse the identifier with a higher sequence number. Candidates get signed, expiring links to pick, reschedule or cancel. Reminders are rows in a jobs table (send at T minus 24 h and T minus 1 h) picked up by whatever scheduler the platform already runs. Every state change is a ledger event.

ponytail: internal availability only. Add external free/busy through CalDAV (`caldav`, Apache-2.0) or a calendar provider's API when interviewers complain that their real calendar is ignored.

**Beyond them.** Panel intersection, fairness rules (the same slots offered to every candidate at a stage), and an auditable history of who moved what.

### 2g. Structured interview scoring

No open-source project stood out here; this area is method, and the evidence is from industrial-organisational psychology.

**What the evidence says.** Sackett et al. (2022) re-estimated selection validities: structured interviews have the highest mean operational validity, 0.42, but with a large spread across studies (standard deviation 0.19), so structure done badly is not protected. Conway, Jako and Goodman (1995), a meta-analysis of 111 inter-rater reliability coefficients, estimated the upper limit of validity at 0.67 for highly structured interviews and 0.34 for unstructured ones; the gap is driven by rater agreement. What "structure" means in that literature: the same job-derived questions for every candidate, anchored rating scales, each question scored separately, raters scoring independently before any discussion.

**Minimum original design (about 350 lines).** A rubric is data: competencies for the role; questions mapped to competencies; for each question a 1 to 5 scale with a written behavioural anchor at each level. A scorecard is one rater's scores for one candidate, with a required evidence note per score, locked on submit. Raters cannot see each other's scorecards until their own is submitted (enforced in code). Aggregation is deterministic: per-competency mean across raters, and a flag wherever raters differ by two or more points, which triggers a discussion rather than an average. Agreement statistics are computed per rubric and per rater pair over time: weighted Cohen's kappa for two raters (statsmodels, BSD-3-Clause), Krippendorff's alpha for ordinal data with missing raters (about 60 lines from the published formula; the Python packages for it are GPL), and a per-rater leniency offset. The model's role is confined to proposing, per rubric anchor, verbatim transcript quotes with timestamps that might be relevant; it produces no score. The human sees the quotes, opens the recording at that point, and scores.

**Beyond them.** Agreement tracked continuously so a rubric with poor agreement is visibly broken and gets rewritten; every score traceable to a quote and a timestamp; a ledger record that the person who decided actually opened the evidence.

---

## 3. Integrity signals

| Signal | How it is measured | Evidence of reliability | Recommended use |
|---|---|---|---|
| Paste into an answer box or code editor | Browser paste event and editor change origin; length, content, time | Measurement is exact. Meaning is ambiguous (own snippet, documentation). | **Show to human**, with the pasted content and what the candidate did next. |
| Edit-history replay of a work sample | Append-only log of editor changes, hash-chained | Measurement is exact; interpretation is by a person watching. | **Show to human.** Strongest single piece of process evidence. |
| Tab or window focus loss | Browser visibility and blur events with durations | Events are accurate, but a second device defeats them completely; the Proctorio experiment found automated flags caught 0 of 6 cheaters. | **Show to human** as a plain timeline fact, never counted or scored. |
| Left full-screen, window resized | Browser events | As above. | **Show to human** as fact only. |
| More than one face in frame | In-browser face detection, count greater than one for a sustained period, with a still | Detection of extra frontal faces is reasonable; skin-tone bias is documented for face detection in proctoring (flag time 7.64% vs 1.56%). | **Show to human** only for "extra face", with the frame. |
| No face detected / face lost | Face detection | Biased against darker skin tones (Yoder-Himes 2022; Burgess 2022); also triggered by lighting and camera angle. | **Do not use.** |
| Speech on the candidate's microphone not matching the candidate | Per-channel recording, far-end masking, speaker-embedding comparison to enrolment | Open diarisation error is 11 to 27% on meeting and telephone benchmarks; shared homes and background noise are common. Our masking design is untested. | **Show to human** as a playable clip. Never a score. Measure our own false-positive rate before relying on it. |
| Gaze direction, "looking off-screen" | Webcam gaze estimation | Error of 2 to 4.5 degrees and worse with movement; cannot separate reading from thinking or from a second monitor used legitimately; no validation in interviews found. | **Do not use.** |
| "Reading from screen" delivery cues (flat prosody, eye scanning) | Audio or video classifier, or rater impression | Human raters gave the same delivery ratings to chatbot-assisted and unassisted candidates (N = 245). No validated classifier found. | **Do not use.** |
| Answer-latency patterns (uniform delay before each answer) | Time from end of question to start of answer | No published validation found. Confounded by thinking style, second-language processing and network delay. | **Do not use as a signal.** Raw latencies may sit in the transcript view without interpretation. |
| Keystroke rhythm classifier (composed vs transcribed) | Key timing features into a trained model | 74.98 to 85.72% when the condition is known, 52.24 to 80.54% when not; paraphrasing and deliberate manipulation are often classed as genuine. | **Do not use** as a classifier. Descriptive counts (pauses, revisions) may appear beside the replay. |
| AI-generated-text detector score | Perplexity-style or trained classifier on the text | 61.3% average false positives on non-native English essays; vendor's own tool withdrawn at 26% true / 9% false positives; 14 tools all under 80% accuracy; easily defeated by paraphrasing. | **Do not use.** Not as a score, not as a hint. |
| Emotion or facial-expression analysis | Video classifier | No evidence of validity for hiring was found or sought; high legal and fairness risk. | **Do not use.** |
| Resume-versus-interview inconsistency | Deterministic comparison of extracted facts, both sources quoted | Extraction can be wrong, so every item must show its two source quotes. The comparison itself is exact. | **Show to human** as "these two statements differ". |
| Depth under follow-up on own answer | Human rating against the rubric of a follow-up that quotes the candidate | Rests on structured-interview validity (0.42) rather than on any detection study. | **Use as interview design**, scored by the human like any other answer. |
| Ability to modify own submitted work live | Human observation plus the edit log | Work samples are among the strongest predictors; no specific study of this as an anti-cheating step was found. | **Use as interview design.** |

Rule that follows from the table: nothing in the "do not use" rows is computed at all, so it cannot leak into a dashboard later.

---

## 4. Open questions and unverified items

**Not verified in this session (stated from memory or estimated):**

1. Latency figures for a local voice loop in 2b are my estimate, not a measurement.
2. India's data-protection law (the Digital Personal Data Protection Act and its rules) was not looked up. Recording, voice embeddings and face detection all need a consent and retention design reviewed against it before build.
3. Whether Kokoro's voices cover Hindi adequately; whether Whisper-family models are accurate enough on Indian-accented English and Hindi-English code-switching. Needs a small in-house test set.
4. pyannote `community-1` internals beyond what the README states (the exact clustering method) were not read.
5. Whether microsandbox runs on Apple Silicon without extra setup.
6. Where CodeMirror development moved after its GitHub repositories were archived.
7. The exact formulation of the Conway et al. figures comes from the abstract as quoted by indexing sites (0.67 and 0.34 are "upper limits of validity", not reliabilities); the full paper was not read.
8. The judge0 vulnerability mechanics are from the public CVE summaries, not from source.
9. The Jabarian and Henkel field-experiment numbers are from the authors' summary page and working-paper listing, not the full paper.
10. `python-caldav/caldav` is reported as Apache-2.0 by the API; the licence file was not opened to check for dual licensing.
11. Stars and push dates are a snapshot of 2026-11-11.

**Open questions for the brief:**

1. No evidence was found that adaptive follow-ups or "modify your own code" measurably reduce successful cheating. They are well-reasoned and cheap, but we should say "designed to" rather than "proven to", and log enough to measure it ourselves.
2. No controlled study of detecting AI assistance in live, two-way interviews was found. The published work covers recorded one-way interviews and exams.
3. The far-end masking plus enrolment approach to second-voice detection is our own design and has no published error rate. It needs a labelled test set from Indian home environments before any reviewer sees its output.
4. Is the first deployment machine a Mac or a Linux host? It decides the sandbox (Docker's virtual machine versus gVisor or nsjail) and the speech runtime (whisper.cpp with Metal versus faster-whisper).
5. Should candidates be allowed AI tools in work samples for some roles? It changes the rubric and removes much of the integrity problem.
6. Gated model downloads (pyannote, AI4Bharat) need a one-time account and acceptance of conditions; someone has to own that, and CC-BY weights need an attribution notice in the product.
7. An AI interviewer changes who applies and who drops out; the field experiment suggests no harm, but it was one firm and one job family.

**Sources cited (all fetched this session unless listed above):** Liang et al. 2023, *Patterns* (arXiv 2304.02819); the vendor announcement withdrawing its classifier (July 2023); Weber-Wulff et al. 2023, *Int. J. Educational Integrity* 19:26 (arXiv 2306.15666); Dugan et al. 2024, RAID, ACL (arXiv 2405.07940); Krishna et al. 2023 (arXiv 2303.13408); Sadasivan et al. 2023 (arXiv 2303.11156); Hans et al. 2024, Binoculars (arXiv 2401.12070); Bergmans et al. 2021, CSEDU (doi 10.5220/0010399602790290); Burgess et al. 2022, USENIX Security (arXiv 2205.03009); Yoder-Himes et al. 2022, *Frontiers in Education* (doi 10.3389/feduc.2022.881449); Papoutsaki et al. 2016, WebGazer, IJCAI; "How Well Does Webcam Eye Tracking Work in the Wild?" (arXiv 2611.04946); Kundu et al. 2024 (arXiv 2406.15335); Mehta et al. 2025 (arXiv 2511.12468); "Detecting LLM-Assisted Vietnamese Writing via Keystrokes" (arXiv 2610.07700); Canagasuriam and Lukacik 2024, *Int. J. Selection and Assessment* (doi 10.1111/ijsa.12491); Jabarian and Henkel 2025, "Voice AI in Firms" (SSRN 5395709); Sackett et al. 2022, *J. Applied Psychology*; Conway, Jako and Goodman 1995, *J. Applied Psychology* 80(5); TamilEOT (arXiv 2609.05631); CVE-2024-28185, CVE-2024-28189, CVE-2024-29021.
