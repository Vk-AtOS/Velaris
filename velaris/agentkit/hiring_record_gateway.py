"""Participant-side entry points of the interview record, as plain functions for a gateway (a candidate's or interviewer's browser).
They authenticate by a session token (random, returned once, stored only as SHA-256, expiring), not by an identity assertion, and are not
in the identity-authenticated API. Every call is gated by that participant's recorded consent.
"""
from __future__ import annotations

import os
import secrets
from typing import Any, Dict, Optional

from velaris.agentkit import hiring_record as hr
from velaris.agentkit.hiring_common import HiringError, audit, bad, hid, need_text, now, sha
from velaris.agentkit.results import fail, ok

PUBLIC = ["POST /interview/{token}/consent  -> candidate_consent", "POST /interview/{token}/events  -> ingest_event",
          "POST /interview/{token}/withdraw -> candidate_withdraw", "POST /interview/{token}/audio    -> audio_precheck + ingest_audio_file"]
# served by velaris.api.public.create_public_app. The audio route streams the body to a private temp file under its own limits
# (size, rate, concurrency) and seals it chunk by chunk; ingest_audio (bytes in memory) stays for callers that already hold the data.


def issue_token(d: Dict[str, Any], org: str, session_id: str, participant: str, hours: int) -> str:
    if isinstance(hours, bool) or not isinstance(hours, int) or not 1 <= hours <= 72:
        raise bad("hours must be 1 to 72")
    raw = secrets.token_urlsafe(24)
    d["tokens"][sha(raw)] = {"org": org, "session_id": session_id, "participant": participant, "expires": now() + hours * 3600}
    return raw


def _open(d: Dict[str, Any], token: Any):
    t = d["tokens"].get(sha(token)) if isinstance(token, str) and 20 <= len(token) <= 80 else None
    s = d["sessions"].get(t["session_id"]) if t else None
    if not t or t["expires"] < now() or not s or s["org"] != t["org"] or s["status"] != "open":
        raise HiringError("not_found", "this link is not valid or has expired")
    return t, s


def set_consent(s: Dict[str, Any], participant: str, scopes: Any, notice_version: Any, at: float) -> Dict[str, Any]:
    if not isinstance(scopes, list) or not scopes or not set(scopes) <= set(hr.SCOPES):
        raise bad(f"scopes must be a non-empty list from {list(hr.SCOPES)}")
    s["consents"][participant] = {"scopes": sorted(set(scopes)), "notice_version": need_text(notice_version, "notice_version", 60),
                                  "at": at, "withdrawn_at": None}
    return s["consents"][participant]


INTERVIEW_NOTICE = "v1"      # the notice text shown on the interview page (public_static/public.js NOTICE); bump both together


def candidate_consent(token: str, scopes: list, notice_version: str) -> Dict[str, Any]:
    try:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            t, s = _open(d, token)
            if notice_version != INTERVIEW_NOTICE:
                raise HiringError("consent_outdated", "the interview notice changed; reload the page and read it again")
            c = set_consent(s, t["participant"], scopes, notice_version, now())
            audit(hr.AGENT, "consent.recorded", t["org"], None, session=hid(t["org"], s["id"]), scopes=",".join(c["scopes"]), notice=c["notice_version"])
            return {"scopes": c["scopes"]}
        return ok(**hr.st().update(go))
    except HiringError as e:
        return fail(e.status, e.reason)


def candidate_withdraw(token: str) -> Dict[str, Any]:
    """Withdraw consent: recording stops at once. What was already recorded is erased through the ATS erasure path."""
    try:
        def go(d: Dict[str, Any]) -> None:
            t, s = _open(d, token)
            if t["participant"] in s["consents"]:
                s["consents"][t["participant"]]["withdrawn_at"] = now()
            audit(hr.AGENT, "consent.withdrawn", t["org"], None, session=hid(t["org"], s["id"]))
        hr.st().update(go)
        return ok(message="Recording has stopped. Ask for erasure of what was recorded; it will be removed.")
    except HiringError as e:
        return fail(e.status, e.reason)


def ingest_event(token: str, event_type: str, data: Optional[Dict[str, Any]] = None, client_t: Any = None) -> Dict[str, Any]:
    try:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            t, s = _open(d, token)
            e = hr.append_event(t["org"], s, t["participant"], event_type, data, client_t)
            s["event_count"], s["chain_head"] = e["seq"], e["hash"]
            return {"seq": e["seq"]}
        return ok(**hr.st().update(go))
    except HiringError as e:
        return fail(e.status, e.reason)


def audio_precheck(token: str) -> Dict[str, Any]:
    """Is this link valid and has the participant consented to audio (and not uploaded yet)? Called before the body is read."""
    try:
        t, s = _open(hr.st().load(), token)
        hr.audio_precheck(s, t["participant"])
        return ok()
    except HiringError as e:
        return fail(e.status, e.reason)


def ingest_audio_file(token: str, src: str, mime: str, duration_s: float) -> Dict[str, Any]:
    """Store an uploaded audio file that is already on disk (see velaris.api.public). Sealing a large file takes seconds, so
    it happens OUTSIDE the store lock; the lock is taken twice, briefly: to read the session and to record the track (re-checked)."""
    try:
        t, s = _open(hr.st().load(), token)
        track = hr.store_audio_file(t["org"], s, t["participant"], src, mime, duration_s)
        created = track.pop("_created", False)

        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            t2, s2 = _open(d, token)                       # the link, consent and "one track" rule may have changed meanwhile
            hr.audio_precheck(s2, t2["participant"])
            s2["tracks"][t2["participant"]] = track
            audit(hr.AGENT, "audio.stored", t2["org"], None, session=hid(t2["org"], s2["id"]), audio_sha256=track["sha256"])
            return {"sha256": track["sha256"]}
        try:
            return ok(**hr.st().update(go))
        except BaseException:                              # nothing references the sealed file: it must not stay behind
            if created and track.get("path"):
                os.unlink(track["path"]) if os.path.exists(track["path"]) else None
            raise
    except HiringError as e:
        return fail(e.status, e.reason)


def ingest_audio(token: str, data: bytes, mime: str, duration_s: float) -> Dict[str, Any]:
    try:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            t, s = _open(d, token)
            if t["participant"] in s["tracks"]:
                raise HiringError("conflict", "this participant already has an audio track: one track per participant")
            track = hr.store_audio(t["org"], s, t["participant"], data, mime, duration_s)
            s["tracks"][t["participant"]] = track
            audit(hr.AGENT, "audio.stored", t["org"], None, session=hid(t["org"], s["id"]), audio_sha256=track["sha256"])
            return {"sha256": track["sha256"]}
        return ok(**hr.st().update(go))
    except HiringError as e:
        return fail(e.status, e.reason)
