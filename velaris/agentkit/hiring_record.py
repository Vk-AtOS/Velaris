"""The replayable interview record: what happened, in order, as facts a person can replay. Never a judgement.

Why there is no "AI-likelihood", "cheating" or "authenticity" score anywhere in this record (research 02, section 2e and 3):
  - AI-text detectors flagged 61.3% of essays by non-native English writers as machine-written (Liang et al. 2023); the best-known vendor
    withdrew its own detector at 26% true / 9% false positives; 14 detectors tested in 2023 all scored under 80% accuracy; paraphrasing
    takes one from 70.3% to 4.6% detection. Every candidate here writes English as an additional language.
  - A widely used proctoring product flagged none of 6 instructed cheaters (sensitivity "very close to zero"); face-not-detected flags
    land 7.64% of exam time on the darkest skin tones against 1.56% on lighter; webcam gaze error is 2 to 4.5 degrees, too coarse to
    tell reading from thinking; keystroke classifiers are a coin toss (52% to 80%) once the writing condition is unknown.
So nothing in those families is computed, and a figure that is never computed cannot leak into a dashboard later. What is kept is exact
measurement: join/leave times, the SIZE of each paste (never its content), an append-only log of edits to a shared pad that can be replayed
to any moment, tab-visibility changes if the client reports them, and one audio track per participant referenced by SHA-256. A named
reviewer may mark an event "relevant" or "explained" with a reason; that mark is a ledger entry. Nothing is counted, thresholded or coloured.

Everything is consent-gated per participant and per scope (events, audio, transcript). Events are an append-only hash chain per session
(each entry holds the hash of the previous one, so an edited or removed entry is detectable). The global ledger gets only the session's
chain head and counts, never text.
"""
from __future__ import annotations

import hashlib
import os
from typing import Any, Callable, Dict, List, Optional

from velaris.agentkit.hiring_common import DAY, HiringError, bad, digest, now, parse_date, store
from velaris.agentkit.state import append_line, read_lines
from velaris.intel.paths import agent_dir, private_dir, write_private

AGENT = "INTERVIEW_RECORD"
SCOPES = ("events", "audio", "transcript")
EVENT_TYPES = ("join", "leave", "paste", "pad_op", "visibility")
MAX_OP_TEXT, MAX_EVENTS = 4000, 50_000
MAX_AUDIO = 200_000_000
GENESIS = "0" * 64
STATEMENT = ("This is a factual, replayable record for a human reviewer. It contains no AI-likelihood, cheating or authenticity score, no threshold "
             "and no colour coding, because those signals are not reliable enough to act on (see the module documentation).")
Transcriber = Callable[[str, str], Dict[str, Any]]


def st() -> Any:
    return store(AGENT, "sessions.json", {"sessions": {}, "tokens": {}})


def _events_path(session_id: str) -> Any:
    return private_dir(agent_dir(AGENT) / "events") / f"{session_id}.jsonl"


def events_of(session_id: str) -> List[Dict[str, Any]]:
    return read_lines(_events_path(session_id))


def verify_chain(events: List[Dict[str, Any]]) -> bool:
    prev = GENESIS
    for e in events:
        body = {k: v for k, v in e.items() if k not in ("hash",)}
        if e["prev"] != prev or e["hash"] != digest(body):
            return False
        prev = e["hash"]
    return True


def expired(s: Dict[str, Any], at: Optional[float] = None) -> bool:
    """True once the session's retention_until date (end of that day) has passed. A session without a readable date counts as expired
    (fail closed): nothing is kept without a retention decision."""
    until = s.get("retention_until")
    try:
        end = parse_date(until, "retention_until") + DAY
    except HiringError:
        return True
    return (now() if at is None else at) >= end


def consented(s: Dict[str, Any], participant: str, scope: str) -> bool:
    c = s["consents"].get(participant)
    return bool(c and scope in c["scopes"] and not c.get("withdrawn_at"))


def _clean_event(kind: str, data: Any) -> Dict[str, Any]:
    if kind not in EVENT_TYPES:
        raise bad(f"event type must be one of {list(EVENT_TYPES)}")
    data = data if isinstance(data, dict) else {}
    if kind in ("join", "leave"):
        return {}
    if kind == "paste":
        n = data.get("size_chars")
        if isinstance(n, bool) or not isinstance(n, int) or not 0 <= n <= 10_000_000:
            raise bad("a paste event carries only size_chars (a whole number)")
        return {"size_chars": n, "target": data.get("target") if data.get("target") in ("pad", "answer", "other") else "other"}
    if kind == "visibility":
        if data.get("state") not in ("hidden", "visible"):
            raise bad("visibility state must be hidden or visible")
        return {"state": data["state"]}
    op = data.get("op")                                                    # pad_op
    pos = data.get("pos")
    if op not in ("insert", "delete") or isinstance(pos, bool) or not isinstance(pos, int) or pos < 0:
        raise bad("pad_op needs op insert|delete and a non-negative integer pos")
    out = {"pad_id": str(data.get("pad_id", "main"))[:40], "op": op, "pos": pos}
    if op == "insert":
        if not isinstance(data.get("text"), str) or not 0 < len(data["text"]) <= MAX_OP_TEXT:
            raise bad(f"an insert carries text of 1 to {MAX_OP_TEXT} characters")
        out["text"] = data["text"]
    else:
        ln = data.get("len")
        if isinstance(ln, bool) or not isinstance(ln, int) or not 0 < ln <= MAX_OP_TEXT:
            raise bad("a delete carries len")
        out["len"] = ln
    return out


def append_event(org: str, s: Dict[str, Any], participant: str, kind: str, data: Any, client_t: Any = None) -> Dict[str, Any]:
    """Append one event to the session's chain. Consent for 'events' from this participant is required."""
    if s["status"] != "open":
        raise HiringError("conflict", "the session is not open")
    if expired(s):
        raise HiringError("denied", "the retention period of this session has ended; nothing more is recorded")
    if not consented(s, participant, "events"):
        raise HiringError("denied", "this participant has not consented to event recording")
    body = _clean_event(kind, data)
    path = _events_path(s["id"])
    prior = read_lines(path)
    if len(prior) >= MAX_EVENTS:
        raise HiringError("conflict", "the session reached its event limit")
    entry = {"seq": len(prior) + 1, "t": now(), "participant": participant, "type": kind, "data": body,
             "client_t": client_t if isinstance(client_t, (int, float)) and not isinstance(client_t, bool) else None,
             "prev": prior[-1]["hash"] if prior else GENESIS}
    entry["hash"] = digest(entry)
    append_line(path, entry)
    return entry


def replay_pad(events: List[Dict[str, Any]], pad_id: str = "main", upto_seq: Optional[int] = None) -> str:
    """Rebuild a shared pad's text by applying its operations in order (deterministic). Positions past the end clamp to the end."""
    text = ""
    for e in events:
        if e["type"] != "pad_op" or e["data"]["pad_id"] != pad_id or (upto_seq is not None and e["seq"] > upto_seq):
            continue
        d, pos = e["data"], min(e["data"]["pos"], len(text))
        text = text[:pos] + d["text"] + text[pos:] if d["op"] == "insert" else text[:pos] + text[pos + d["len"]:]
    return text


def pad_summary(events: List[Dict[str, Any]]) -> Dict[str, Any]:
    ins = [e for e in events if e["type"] == "pad_op" and e["data"]["op"] == "insert"]
    dele = [e for e in events if e["type"] == "pad_op" and e["data"]["op"] == "delete"]
    big = sorted(ins, key=lambda e: -len(e["data"]["text"]))[:5]
    return {"insert_ops": len(ins), "delete_ops": len(dele), "characters_inserted": sum(len(e["data"]["text"]) for e in ins),
            "characters_deleted": sum(e["data"]["len"] for e in dele),
            "five_largest_single_inserts": [{"seq": e["seq"], "participant": e["participant"], "characters": len(e["data"]["text"])} for e in big]}


def store_audio(org: str, s: Dict[str, Any], participant: str, data: bytes, mime: str, duration_s: Any) -> Dict[str, Any]:
    """Write one participant's audio track (owner-only file named by its hash) and return the track record."""
    if not consented(s, participant, "audio"):
        raise HiringError("denied", "this participant has not consented to audio recording")
    if not isinstance(data, (bytes, bytearray)) or not 0 < len(data) <= MAX_AUDIO:
        raise bad("audio must be 1 byte to 200 MB")
    h = hashlib.sha256(bytes(data)).hexdigest()
    path = private_dir(agent_dir(AGENT) / "audio") / f"{h}.bin"
    write_private(path, bytes(data))
    return track_record(participant, h, len(data), mime, duration_s, str(path))


def track_record(participant: str, sha256: str, size: int, mime: str, duration_s: Any, path: Optional[str]) -> Dict[str, Any]:
    if not isinstance(sha256, str) or len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise bad("sha256 must be 64 lowercase hex characters")
    if isinstance(duration_s, bool) or not isinstance(duration_s, (int, float)) or not 0 < duration_s <= 6 * 3600:
        raise bad("duration_s must be seconds, up to 6 hours")
    if mime not in ("audio/wav", "audio/ogg", "audio/webm", "audio/mpeg", "audio/mp4", "audio/flac"):
        raise bad("mime must be an audio type: wav, ogg, webm, mpeg, mp4 or flac")
    return {"participant": participant, "sha256": sha256, "bytes": int(size), "mime": mime, "duration_s": float(duration_s),
            "path": path, "transcript": None, "transcript_status": "not_requested", "registered_at": now()}


def transcribe(track: Dict[str, Any], hook: Optional[Transcriber]) -> Dict[str, Any]:
    """Fill the track's transcript through an optional local hook, or report not_configured. faster-whisper is not installed with
    Velaris: a deployment that adds it passes a function (path, sha256) -> {"language", "segments": [{"start", "end", "text"}]}."""
    if hook is None:
        track["transcript_status"] = "not_configured"
        return track
    if not track.get("path"):
        track["transcript_status"] = "no_local_file"
        return track
    try:
        out = hook(track["path"], track["sha256"])
        segs = [{"start": float(x["start"]), "end": float(x["end"]), "text": str(x["text"])[:2000]} for x in out["segments"]][:20_000]
    except (OSError, KeyError, TypeError, ValueError) as e:
        track["transcript_status"] = f"failed: {type(e).__name__}"
        return track
    track["transcript"] = {"language": str(out.get("language", ""))[:20], "segments": segs}
    track["transcript_status"] = "done"
    return track


def export_candidate(org: str, candidate_id: str) -> Dict[str, Any]:
    d = st().load()
    out = []
    for s in d["sessions"].values():
        if s["org"] == org and s["candidate_id"] == candidate_id:
            out.append({**s, "events": events_of(s["id"])})
    return {"interview_records": out}


def _erase_session(s: Dict[str, Any]) -> None:
    try:
        _events_path(s["id"]).unlink()
    except FileNotFoundError:
        pass
    for t in s["tracks"].values():
        if t.get("path"):
            try:
                os.remove(t["path"])
            except FileNotFoundError:
                pass
    s.update(candidate_id=None, application_id=None, tracks={}, consents={}, marks=[], status="erased", erased_events=s.get("event_count", 0))


def _drop_tokens(d: Dict[str, Any], org: str) -> None:
    for h in [h for h, t in d["tokens"].items() if t["org"] == org and d["sessions"].get(t["session_id"], {}).get("status") == "erased"]:
        del d["tokens"][h]


def purge_candidate(org: str, candidate_id: str) -> int:
    n = 0

    def go(d: Dict[str, Any]) -> None:
        nonlocal n
        for s in d["sessions"].values():
            if s["org"] == org and s["candidate_id"] == candidate_id:
                _erase_session(s)
                n += 1
        _drop_tokens(d, org)
    st().update(go)
    return n


def purge_expired(org: str, at: Optional[float] = None) -> List[str]:
    """Erase every session of `org` whose retention_until has passed (events, audio files, transcripts, consents). Returns their ids."""
    done: List[str] = []

    def go(d: Dict[str, Any]) -> None:
        for s in d["sessions"].values():
            if s["org"] == org and s["status"] != "erased" and expired(s, at):
                _erase_session(s)
                done.append(s["id"])
        _drop_tokens(d, org)
    st().update(go)
    return done
