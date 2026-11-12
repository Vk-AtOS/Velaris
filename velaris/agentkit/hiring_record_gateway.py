"""Participant-side entry points of the interview record, as plain functions for a gateway (a candidate's or interviewer's browser).
They authenticate by a session token (random, returned once, stored only as SHA-256, expiring), not by an identity assertion, and are not
in the identity-authenticated API. Every call is gated by that participant's recorded consent.
"""
from __future__ import annotations

import secrets
from typing import Any, Dict, Optional

from velaris.agentkit import hiring_record as hr
from velaris.agentkit.hiring_common import HiringError, audit, bad, hid, need_text, now, sha
from velaris.agentkit.results import fail, ok

PUBLIC = ["POST /interview/{token}/consent  -> candidate_consent", "POST /interview/{token}/events  -> ingest_event",
          "POST /interview/{token}/withdraw -> candidate_withdraw"]
# served by velaris.api.public.create_public_app. ingest_audio is NOT served there (uploads of up to MAX_AUDIO need a streaming
# ingress with its own limits); until one exists audio tracks are registered by staff (INTERVIEW_RECORD.register_audio_track).


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


def candidate_consent(token: str, scopes: list, notice_version: str) -> Dict[str, Any]:
    try:
        def go(d: Dict[str, Any]) -> Dict[str, Any]:
            t, s = _open(d, token)
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
