"""INTERVIEW_RECORD: a consent-gated, replayable record of an interview for a human reviewer.

Why it contains no AI-likelihood or cheating score, and what it records instead, is written out in velaris.agentkit.hiring_record (short
version: AI-text detectors flag 61.3% of non-native English writing, a proctoring product caught 0 of 6 cheaters, gaze error is 2 to 4.5
degrees; so none of those is computed). Staff methods here create the session, record interviewers' consent, hand out participant tokens,
register audio, run the optional local transcriber and mark events. The participant side (candidate_consent, ingest_event, ingest_audio,
candidate_withdraw in velaris.agentkit.hiring_record_gateway) works from tokens and is not in the identity-authenticated API: event
ingestion at browser speed cannot wait for an approval per event.

The evidence view and replay return personal data (a pad's text, transcripts), so they go through access.authorize_read("identity").
Erasure through ATS_CORE deletes events, audio files and transcripts and keeps only that a session existed.
"""
import importlib.util
import logging
from typing import Any, Dict, Optional

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_record as hr
from velaris.agentkit import hiring_record_gateway as gw
from velaris.agentkit.hiring_common import HIRING, PANEL, HiringError, acts, audit, bad, hid, mine, need_text, now, reads
from velaris.agentkit.results import ok
from velaris.core.access import authorize_read

logger = logging.getLogger("INTERVIEW_RECORD")
AGENT = hr.AGENT


def _session(d: Dict[str, Any], org: str, sid: Any) -> Dict[str, Any]:
    s = d["sessions"].get(str(sid))
    if not s or s["org"] != org:
        raise HiringError("not_found", "no such session")
    return s


def _manages(s: Dict[str, Any], caller: Any) -> None:
    """Only the session's creator, its participants, or a hiring manager / HR admin may act on a session."""
    if caller.id != s["created_by"] and caller.id not in s["participants"] and not caller.roles & (hc.DECIDERS):
        raise HiringError("denied", "you are not connected to this session")


class InterviewRecord:
    """Consent-gated interview event record and evidence view. No judgement of any person is computed."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self._transcriber = self.config.get("transcriber")      # optional (audio_path, sha256) -> {"language", "segments": [...]}

    def health_check(self) -> Dict[str, Any]:
        return {"agent": AGENT, "status": "ok", "transcriber": "configured" if self._transcriber else "not_configured",
                "faster_whisper_installed": importlib.util.find_spec("faster_whisper") is not None}

    @acts(AGENT, HIRING)
    def create_session(self, caller, application_id: str, interviewer_ids: list, retention_days: int = 90) -> Dict[str, Any]:
        """Open a record for one interview of an application. Participants: 'candidate' and the interviewers. Nothing is recorded until
        each participant has consented."""
        org = caller.org
        app = hc.application_known(org, application_id)
        if not app or not app.get("candidate_id"):
            raise HiringError("not_found", "no such application")
        if (not isinstance(interviewer_ids, list) or not 1 <= len(interviewer_ids) <= 6 or "candidate" in interviewer_ids
                or len(set(interviewer_ids)) != len(interviewer_ids)):
            raise bad("interviewer_ids must be 1 to 6 distinct ids")
        if isinstance(retention_days, bool) or not isinstance(retention_days, int) or not 1 <= retention_days <= 365:
            raise bad("retention_days must be 1 to 365")
        sid = hc.new_id("sess")
        rec = {"id": sid, "org": org, "application_id": application_id, "candidate_id": app["candidate_id"], "status": "open",
               "participants": ["candidate", *map(str, interviewer_ids)], "consents": {}, "tracks": {}, "marks": [], "event_count": 0,
               "chain_head": hr.GENESIS, "created_by": caller.id, "created_at": now(), "retention_until": hc.iso(now() + retention_days * hc.DAY)[:10]}

        def go(d: Dict[str, Any]) -> None:
            audit(AGENT, "session.created", org, caller, session=hid(org, sid), application=hid(org, application_id))
            d["sessions"][sid] = rec
        hr.st().update(go)
        return ok(session=rec)

    @acts(AGENT, PANEL)
    def give_consent(self, caller, session_id: str, scopes: list, notice_version: str) -> Dict[str, Any]:
        """Your own consent to be recorded (scopes: events, audio, transcript). Only for yourself."""
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            s = _session(d, caller.org, session_id)
            if caller.id not in s["participants"] or s["status"] != "open":
                raise HiringError("denied", "you are not a participant of an open session")
            c = gw.set_consent(s, caller.id, scopes, notice_version, now())
            audit(AGENT, "consent.recorded", caller.org, caller, session=hid(caller.org, session_id), scopes=",".join(c["scopes"]), notice=c["notice_version"])
            return c
        return ok(consent=hr.st().update(go))

    @acts(AGENT, PANEL)
    def withdraw_my_consent(self, caller, session_id: str) -> Dict[str, Any]:
        def go(d: Dict[str, Any]) -> None:
            s = _session(d, caller.org, session_id)
            if caller.id not in s["consents"]:
                raise HiringError("not_found", "you have not consented")
            audit(AGENT, "consent.withdrawn", caller.org, caller, session=hid(caller.org, session_id))
            s["consents"][caller.id]["withdrawn_at"] = now()
        hr.st().update(go)
        return ok(message="Recording of you has stopped.")

    @acts(AGENT, HIRING)
    def issue_participant_token(self, caller, session_id: str, participant: str = "candidate", hours: int = 12) -> Dict[str, Any]:
        """A token for a participant's browser (returned once, stored hashed, expiring). Works with the gateway functions."""
        def go(d: Dict[str, Any]) -> str:
            s = _session(d, caller.org, session_id)
            _manages(s, caller)
            if participant not in s["participants"] or s["status"] != "open":
                raise HiringError("not_found", "no such participant in an open session")
            audit(AGENT, "token.issued", caller.org, caller, session=hid(caller.org, session_id), participant=hid(caller.org, participant))
            return gw.issue_token(d, caller.org, session_id, participant, hours)
        return ok(token=hr.st().update(go), gateway_functions=gw.PUBLIC)

    @acts(AGENT, HIRING)
    def register_audio_track(self, caller, session_id: str, participant: str, sha256: str, size_bytes: int, duration_s: float, mime: str) -> Dict[str, Any]:
        """Reference an audio track that lives in the recorder's own store, by its SHA-256 (one per participant; consent for audio needed)."""
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            s = _session(d, caller.org, session_id)
            _manages(s, caller)
            if participant not in s["participants"]:
                raise HiringError("not_found", "no such participant")
            if not hr.consented(s, participant, "audio"):
                raise HiringError("denied", "this participant has not consented to audio recording")
            if participant in s["tracks"]:
                raise HiringError("conflict", "one audio track per participant")
            t = hr.track_record(participant, sha256, size_bytes, mime, duration_s, None)
            audit(AGENT, "audio.registered", caller.org, caller, session=hid(caller.org, session_id), audio_sha256=sha256)
            s["tracks"][participant] = t
            return {k: v for k, v in t.items() if k != "path"}
        return ok(track=hr.st().update(go))

    @acts(AGENT, HIRING)
    def transcribe_track(self, caller, session_id: str, participant: str) -> Dict[str, Any]:
        """Fill the transcript with the local transcriber hook, or report not_configured (the field stays empty). Needs transcript consent."""
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            s = _session(d, caller.org, session_id)
            _manages(s, caller)
            t = s["tracks"].get(participant)
            if not t:
                raise HiringError("not_found", "no audio track for this participant")
            if not hr.consented(s, participant, "transcript"):
                raise HiringError("denied", "this participant has not consented to transcription")
            hr.transcribe(t, self._transcriber)
            audit(AGENT, "transcription", caller.org, caller, session=hid(caller.org, session_id), status=t["transcript_status"].split(":")[0])
            return {"participant": participant, "transcript_status": t["transcript_status"]}
        return ok(**hr.st().update(go))

    @acts(AGENT, HIRING)
    def close_session(self, caller, session_id: str) -> Dict[str, Any]:
        """Close the session. The ledger gets the chain head hash and counts, never content."""
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            s = _session(d, caller.org, session_id)
            _manages(s, caller)
            if s["status"] != "open":
                raise HiringError("conflict", f"session is {s['status']}")
            audit(AGENT, "session.closed", caller.org, caller, session=hid(caller.org, session_id), events=s["event_count"], chain_head=s["chain_head"])
            s["status"] = "closed"
            return {"events": s["event_count"], "chain_head": s["chain_head"]}
        return ok(**hr.st().update(go))

    @acts(AGENT, HIRING)
    def mark_event(self, caller, session_id: str, seq: int, mark: str, reason: str) -> Dict[str, Any]:
        """A named reviewer marks an event 'relevant' or 'explained', with a reason. The mark is a ledger entry; it changes nothing else."""
        if mark not in ("relevant", "explained"):
            raise bad("mark must be relevant or explained")
        reason = need_text(reason, "reason", 500)

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            s = _session(d, caller.org, session_id)
            _manages(s, caller)
            if isinstance(seq, bool) or not isinstance(seq, int) or not 1 <= seq <= s["event_count"]:
                raise bad("seq must be an existing event number")
            m = {"seq": seq, "mark": mark, "reason": reason, "by": caller.id, "at": now()}
            audit(AGENT, "event.marked", caller.org, caller, session=hid(caller.org, session_id), seq=seq, mark=mark, reason_sha256=hc.sha(reason))
            s["marks"].append(m)
            return m
        return ok(mark=hr.st().update(go))

    @acts(AGENT, frozenset())
    def purge_expired_sessions(self, caller) -> Dict[str, Any]:
        """Erase every session of the organisation past its retention_until date: events, audio, transcripts, consents (HR admins).
        Reads of an expired session are refused until this runs; an expired session accepts no new events."""
        done = hr.purge_expired(caller.org)
        audit(AGENT, "retention.purged", caller.org, caller, sessions=len(done), ids=hc.digest(done))
        return ok(erased_sessions=done)

    # ---- reading ------------------------------------------------------------------------------------------------
    @reads(AGENT, HIRING)
    def list_sessions(self, caller, application_id: str = "") -> Dict[str, Any]:
        """Sessions with counts only: no content, no names."""
        return ok(sessions=[{"id": s["id"], "application_id": s["application_id"], "status": s["status"], "events": s["event_count"],
                             "tracks": len(s["tracks"]), "retention_until": s["retention_until"]}
                            for s in mine(hr.st().load()["sessions"].values(), caller.org) if not application_id or s["application_id"] == application_id])

    def _for_review(self, caller, session_id: str) -> Dict[str, Any]:
        s = _session(hr.st().load(), caller.org, session_id)
        if s["status"] != "erased" and hr.expired(s):
            raise HiringError("retention_expired", "the retention period of this session has ended; it is erased by purge_expired_sessions")
        authorize_read("identity", s["candidate_id"] or session_id, agent=AGENT, caller=caller, org=caller.org)
        return s

    @reads(AGENT, HIRING)
    def evidence_view(self, caller, session_id: str) -> Dict[str, Any]:
        """For a human reviewer: consent, the time-ordered events, pad edit summary, audio tracks by hash, transcript status and the
        reviewers' marks. Facts only: no score, no threshold, no colour, no model-written judgement. Identity data: authorize_read."""
        s = self._for_review(caller, session_id)
        ev = hr.events_of(s["id"])
        timeline = [{"seq": e["seq"], "at": hc.iso(e["t"]), "participant": e["participant"], "type": e["type"],
                     **({"size_chars": e["data"]["size_chars"], "target": e["data"]["target"]} if e["type"] == "paste" else {}),
                     **({"state": e["data"]["state"]} if e["type"] == "visibility" else {}),
                     **({"pad": e["data"]["pad_id"], "op": e["data"]["op"], "characters": len(e["data"].get("text", "")) or e["data"].get("len")} if e["type"] == "pad_op" else {}),
                     "client_reported_time": e["client_t"]} for e in ev]
        return ok(session_id=s["id"], status=s["status"],
                  consents={p: {"scopes": c["scopes"], "notice_version": c["notice_version"], "withdrawn": bool(c.get("withdrawn_at"))} for p, c in s["consents"].items()},
                  timeline=timeline, pad_edit_summary=hr.pad_summary(ev), hash_chain_intact=hr.verify_chain(ev),
                  audio_tracks=[{k: v for k, v in t.items() if k not in ("path", "transcript")} for t in s["tracks"].values()],
                  transcripts={p: t["transcript"] for p, t in s["tracks"].items() if t["transcript"]},
                  reviewer_marks=s["marks"], statement=hr.STATEMENT)

    @reads(AGENT, HIRING)
    def replay_pad(self, caller, session_id: str, pad_id: str = "main", upto_seq: int = 0) -> Dict[str, Any]:
        """The shared pad's text as it stood after event `upto_seq` (0 = the end), rebuilt from the operation log."""
        s = self._for_review(caller, session_id)
        ev = hr.events_of(s["id"])
        if not hr.verify_chain(ev):
            raise HiringError("integrity", "the event chain does not verify; the record was altered")
        return ok(pad_id=pad_id, upto_seq=upto_seq or len(ev), text=hr.replay_pad(ev, pad_id, upto_seq or None), statement=hr.STATEMENT)
