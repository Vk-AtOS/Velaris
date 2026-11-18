"""INTERVIEW_RECORD: consent-gated events, replayable pad log, audio by hash, transcriber hook, evidence view with no score of any kind."""
from velaris.agentkit.state import append_line
import hashlib
import json
import os

import pytest
from velaris.agentkit.hiring_testkit import ORG, as_, bootstrap, clean_keys, consent, trace_text, who

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_record as hr
from velaris.agentkit import hiring_record_gateway as gw
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.agents.INTERVIEW_RECORD.main import InterviewRecord
from velaris.core import vault
from velaris.intel.paths import agent_dir

NO_SCORES = ("score", "suspicio", "flagged", "risk", "honest", "integrity", "anomal", "confidence")


@pytest.fixture()
def env():
    ats, rec = AtsCore(), InterviewRecord()
    rid, c = bootstrap(ats)
    with as_(c["rec"]):
        r = ats.add_candidate(name="Asha Kumar", email="asha@example.com", source="careers_page", requisition_id=rid, consent=consent())
        app, cid = r["application"]["id"], r["candidate_id"]
        sess = rec.create_session(application_id=app, interviewer_ids=["iv-1"])["session"]["id"]
        tok = rec.issue_participant_token(session_id=sess)["token"]
        itok = rec.issue_participant_token(session_id=sess, participant="iv-1")["token"]
    return ats, rec, sess, tok, itok, cid, c


def consent_all(rec, sess, tok, scopes=("events", "audio", "transcript")):
    assert gw.candidate_consent(tok, list(scopes), "v1")["status"] == "ok"


def stored_events(sess):
    return hr.events_of(sess)


def test_nothing_is_recorded_without_consent_and_consent_is_per_participant_and_scope(env):
    ats, rec, sess, tok, itok, cid, c = env
    assert gw.ingest_event(tok, "join")["status"] == "denied"
    assert not (agent_dir("INTERVIEW_RECORD") / "events" / f"{sess}.jsonl").exists()
    assert gw.candidate_consent(tok, ["telepathy"], "v1")["status"] == "invalid_input" and gw.candidate_consent(tok, [], "v1")["status"] == "invalid_input"
    assert gw.candidate_consent(tok, ["audio"], "v1")["status"] == "ok"
    assert gw.ingest_event(tok, "join")["status"] == "denied"                                   # audio consent is not events consent
    assert gw.ingest_audio(tok, b"RIFF....", "audio/wav", 3.0)["status"] == "ok"
    consent_all(rec, sess, tok, ("events",))
    assert gw.ingest_event(tok, "join")["seq"] == 1
    assert gw.ingest_event(itok, "join")["status"] == "denied"                                  # the interviewer has not consented yet
    with as_(who("interviewer", id="iv-1")):
        assert rec.give_consent(session_id=sess, scopes=["events"], notice_version="v1")["status"] == "ok"
    with as_(who("interviewer", id="iv-2")):
        assert rec.give_consent(session_id=sess, scopes=["events"], notice_version="v1")["status"] == "denied"      # not a participant
    assert gw.ingest_event(itok, "join")["seq"] == 2
    assert gw.ingest_event("x" * 30, "join")["status"] == "not_found" and gw.ingest_event(None, "join")["status"] == "not_found"
    s = {c: dict(hr.st().load()[c]) for c in ("sessions", "tokens")}
    assert tok not in json.dumps(s) and hc.sha(tok) in s["tokens"] and s["sessions"][sess]["org"] == ORG
    assert s["sessions"][sess]["consents"]["candidate"]["notice_version"] == "v1"


def test_event_types_are_whitelisted_pastes_carry_size_only(env):
    ats, rec, sess, tok, itok, cid, c = env
    consent_all(rec, sess, tok)
    assert gw.ingest_event(tok, "paste", {"size_chars": 840, "target": "pad", "text": "SECRET PASTED TEXT", "content": "more"})["status"] == "ok"
    assert gw.ingest_event(tok, "paste", {"text": "no size"})["status"] == "invalid_input" and gw.ingest_event(tok, "paste", {"size_chars": True})["status"] == "invalid_input"
    assert gw.ingest_event(tok, "visibility", {"state": "hidden"}, client_t=12.5)["status"] == "ok" and gw.ingest_event(tok, "visibility", {"state": "gaze_off"})["status"] == "invalid_input"
    for kind in ("ai_likelihood", "keystroke_rhythm", "face_count", "gaze", "cheating_score"):
        assert gw.ingest_event(tok, kind, {"value": 0.9})["status"] == "invalid_input", kind        # signals we refuse to record at all
    assert gw.ingest_event(tok, "pad_op", {"op": "insert", "pos": 0})["status"] == "invalid_input"
    assert gw.ingest_event(tok, "pad_op", {"op": "insert", "pos": -1, "text": "x"})["status"] == "invalid_input"
    ev = stored_events(sess)
    assert [e["type"] for e in ev] == ["paste", "visibility"] and ev[0]["data"] == {"size_chars": 840, "target": "pad"}
    assert "SECRET PASTED TEXT" not in (agent_dir("INTERVIEW_RECORD") / "events" / f"{sess}.jsonl").read_text()
    assert ev[1]["client_t"] == 12.5 and oct((agent_dir("INTERVIEW_RECORD") / "events" / f"{sess}.jsonl").stat().st_mode & 0o777) == "0o600"


def test_pad_edit_log_replays_to_any_moment_and_the_chain_detects_tampering(env):
    ats, rec, sess, tok, itok, cid, c = env
    consent_all(rec, sess, tok)
    ops = [{"op": "insert", "pos": 0, "text": "def f(x):"}, {"op": "insert", "pos": 9, "text": "\n    return x"}, {"op": "insert", "pos": 9, "text": " # note"},
           {"op": "delete", "pos": 9, "len": 7}, {"op": "insert", "pos": 99, "text": "!"}]           # a position past the end clamps to the end
    for o in ops:
        assert gw.ingest_event(tok, "pad_op", {"pad_id": "main", **o})["status"] == "ok"
    gw.ingest_event(tok, "pad_op", {"pad_id": "other", "op": "insert", "pos": 0, "text": "scratch"})
    ev = stored_events(sess)
    assert hr.replay_pad(ev, "main") == "def f(x):\n    return x!"
    assert hr.replay_pad(ev, "main", upto_seq=1) == "def f(x):" and hr.replay_pad(ev, "main", upto_seq=3) == "def f(x): # note\n    return x"
    assert hr.replay_pad(ev, "other") == "scratch" and hr.replay_pad([], "main") == ""
    assert hr.verify_chain(ev) and [e["seq"] for e in ev] == [1, 2, 3, 4, 5, 6]
    with as_(c["adm"]):
        v = rec.evidence_view(session_id=sess)
        assert v["hash_chain_intact"] is True and v["pad_edit_summary"]["insert_ops"] == 5 and v["pad_edit_summary"]["characters_deleted"] == 7
        assert v["pad_edit_summary"]["five_largest_single_inserts"][0] == {"seq": 2, "participant": "candidate", "characters": 13}
        assert rec.replay_pad(session_id=sess, upto_seq=2)["text"] == "def f(x):\n    return x"
        assert rec.replay_pad(session_id=sess)["text"] == "def f(x):\n    return x!"
    p = agent_dir("INTERVIEW_RECORD") / "events" / f"{sess}.jsonl"
    assert "VLV2:" in p.read_text()                                                                # events are sealed at rest
    lines = [json.dumps(e, sort_keys=True) for e in stored_events(sess)]
    forged = json.loads(lines[1])
    forged["data"]["text"] = "\n    return 0"                                                        # edit history after the fact
    lines[1] = json.dumps(forged, sort_keys=True)
    def rewrite(ls):                                   # an insider with the key rewrites the sealed log
        p.unlink()
        for line in ls:
            append_line(p, json.loads(line), encrypted=hr._SEAL)
    rewrite(lines)
    assert hr.verify_chain(stored_events(sess)) is False
    with as_(c["adm"]):
        assert rec.evidence_view(session_id=sess)["hash_chain_intact"] is False
        assert rec.replay_pad(session_id=sess)["status"] == "integrity"
    rewrite(lines[:1] + lines[2:])                                            # a removed entry is detected too
    assert hr.verify_chain(stored_events(sess)) is False


def test_one_audio_track_per_participant_referenced_by_hash(env):
    ats, rec, sess, tok, itok, cid, c = env
    consent_all(rec, sess, tok)
    data = b"RIFF" + os.urandom(64)
    r = gw.ingest_audio(tok, data, "audio/wav", 61.5)
    assert r["status"] == "ok" and r["sha256"] == hashlib.sha256(data).hexdigest()
    path = agent_dir("INTERVIEW_RECORD") / "audio" / f"{r['sha256']}.bin"
    assert path.read_bytes() != data and vault.read_sealed(path, "hiring:INTERVIEW_RECORD", vault.path_context(path)) == data and oct(path.stat().st_mode & 0o777) == "0o600"
    assert gw.ingest_audio(tok, data, "audio/wav", 61.5)["status"] == "conflict"                     # one per participant
    assert gw.ingest_audio(itok, data, "audio/wav", 5)["status"] == "denied"                         # the interviewer has not consented
    with as_(who("interviewer", id="iv-1")):
        rec.give_consent(session_id=sess, scopes=["audio", "events"], notice_version="v1")
    assert gw.ingest_audio(itok, data, "video/mp4", 5)["status"] == "invalid_input" and gw.ingest_audio(itok, b"", "audio/wav", 5)["status"] == "invalid_input"
    assert gw.ingest_audio(itok, data, "audio/wav", 0)["status"] == "invalid_input"
    with as_(c["rec"]):
        assert rec.register_audio_track(session_id=sess, participant="iv-1", sha256="zz", size_bytes=1, duration_s=1, mime="audio/ogg")["status"] == "invalid_input"
        ext = rec.register_audio_track(session_id=sess, participant="iv-1", sha256="a" * 64, size_bytes=10, duration_s=9.0, mime="audio/ogg")
        assert ext["status"] == "ok" and "path" not in ext["track"]                                   # registered by hash only, from the recorder's own store
        assert rec.register_audio_track(session_id=sess, participant="iv-1", sha256="b" * 64, size_bytes=10, duration_s=9.0, mime="audio/ogg")["status"] == "conflict"
    with as_(c["adm"]):
        v = rec.evidence_view(session_id=sess)
    assert [t["participant"] for t in v["audio_tracks"]] == ["candidate", "iv-1"] and all("path" not in t for t in v["audio_tracks"])


def test_transcriber_hook_reports_not_configured_by_default_and_fills_the_field_when_given(env, tmp_path):
    ats, rec, sess, tok, itok, cid, c = env
    consent_all(rec, sess, tok)
    gw.ingest_audio(tok, b"RIFFdata", "audio/wav", 4.0)
    assert rec.health_check()["transcriber"] == "not_configured" and rec.health_check()["faster_whisper_installed"] is False
    with as_(c["rec"]):
        r = rec.transcribe_track(session_id=sess, participant="candidate")
        assert r["status"] == "ok" and r["transcript_status"] == "not_configured"
        assert rec.transcribe_track(session_id=sess, participant="iv-1")["status"] == "not_found"
    with as_(c["adm"]):
        v = rec.evidence_view(session_id=sess)
    assert v["transcripts"] == {} and v["audio_tracks"][0]["transcript_status"] == "not_configured"
    calls = []

    def hook(path, sha):
        calls.append((os.path.basename(path), sha))
        return {"language": "en", "segments": [{"start": 0, "end": 1.5, "text": "Hello, I am Asha."}]}
    rec2 = InterviewRecord({"transcriber": hook})
    with as_(c["rec"]):
        assert rec2.transcribe_track(session_id=sess, participant="candidate")["transcript_status"] == "done"
    assert calls and calls[0][1] == hashlib.sha256(b"RIFFdata").hexdigest()
    with as_(c["adm"]):
        assert rec2.evidence_view(session_id=sess)["transcripts"]["candidate"]["segments"][0]["text"] == "Hello, I am Asha."
    boom = InterviewRecord({"transcriber": lambda p, s: (_ for _ in ()).throw(ValueError("model missing"))})
    with as_(c["rec"]):
        assert boom.transcribe_track(session_id=sess, participant="candidate")["transcript_status"] == "failed: ValueError"
    # transcription needs the participant's consent to it: a second session where only audio was consented
    with as_(c["rec"]):
        app = next(iter(json.loads((agent_dir("ATS_CORE") / "evaluation.json").read_text())["applications"]))
        sess2 = rec2.create_session(application_id=app, interviewer_ids=["iv-1"])["session"]["id"]
        tok2 = rec2.issue_participant_token(session_id=sess2)["token"]
    assert gw.candidate_consent(tok2, ["audio"], "v1")["status"] == "ok" and gw.ingest_audio(tok2, b"RIFFmore", "audio/wav", 2.0)["status"] == "ok"
    with as_(c["rec"]):
        assert rec2.transcribe_track(session_id=sess2, participant="candidate")["status"] == "denied"


def test_evidence_view_is_facts_for_a_human_with_no_score_of_any_kind(env):
    ats, rec, sess, tok, itok, cid, c = env
    consent_all(rec, sess, tok)
    for kind, data in (("join", {}), ("paste", {"size_chars": 5000, "target": "answer"}), ("visibility", {"state": "hidden"}), ("visibility", {"state": "visible"}),
                       ("pad_op", {"op": "insert", "pos": 0, "text": "print('hi')"}), ("leave", {})):
        assert gw.ingest_event(tok, kind, data)["status"] == "ok"
    with as_(c["rec"]):
        assert rec.evidence_view(session_id=sess)["status"] == "denied"                                # identity data: recruiter has no 'identity' read
        assert rec.list_sessions()["sessions"][0]["events"] == 6
    with as_(c["adm"]):
        v = rec.evidence_view(session_id=sess)
        assert [(e["type"], e.get("size_chars"), e.get("state")) for e in v["timeline"]] == [("join", None, None), ("paste", 5000, None), ("visibility", None, "hidden"),
                                                                                           ("visibility", None, "visible"), ("pad_op", None, None), ("leave", None, None)]
        assert v["consents"]["candidate"]["scopes"] == ["audio", "events", "transcript"] and "no AI-likelihood" in v["statement"] and "no colour coding" in v["statement"]
        mark = rec.mark_event(session_id=sess, seq=3, mark="explained", reason="Candidate said a doorbell rang")
        assert mark["mark"]["by"] == "hr_admin-1" and rec.mark_event(session_id=sess, seq=99, mark="relevant", reason="x")["status"] == "invalid_input"
        assert rec.mark_event(session_id=sess, seq=3, mark="suspicious", reason="x")["status"] == "invalid_input" and rec.mark_event(session_id=sess, seq=3, mark="relevant", reason="")["status"] == "invalid_input"
        v2 = rec.evidence_view(session_id=sess)
    assert v2["reviewer_marks"][0]["reason"] == "Candidate said a doorbell rang"
    clean_keys(v2, NO_SCORES)
    t = trace_text()
    assert "event.marked" in t and "doorbell" not in t and "print(" not in t and "Asha" not in t        # the ledger holds the mark's hash, never text


def test_close_withdraw_and_erasure(env):
    ats, rec, sess, tok, itok, cid, c = env
    consent_all(rec, sess, tok)
    gw.ingest_event(tok, "join")
    gw.ingest_event(tok, "pad_op", {"op": "insert", "pos": 0, "text": "private pad text"})
    gw.ingest_audio(tok, b"RIFFsecretaudio", "audio/wav", 10)
    assert gw.candidate_withdraw(tok)["status"] == "ok"
    assert gw.ingest_event(tok, "leave")["status"] == "denied" and len(stored_events(sess)) == 2        # recording stopped at once
    with as_(c["rec"]):
        closed = rec.close_session(session_id=sess)
        assert closed["status"] == "ok" and closed["events"] == 2 and len(closed["chain_head"]) == 64
        assert rec.close_session(session_id=sess)["status"] == "conflict"
    assert gw.ingest_event(itok, "join")["status"] == "not_found"                                       # closed
    with as_(c["adm"]):
        assert "private pad text" in json.dumps(ats.export_candidate(candidate_id=cid)["export"]["interview_records"])
        assert ats.erase_candidates(candidate_ids=[cid], reason="erasure_request")["removed_by_module"]["hiring_record"] == 1
        v = rec.list_sessions()["sessions"][0]
    assert v["status"] == "erased" and v["events"] == 2 and v["tracks"] == 0
    assert not (agent_dir("INTERVIEW_RECORD") / "events" / f"{sess}.jsonl").exists()
    assert list((agent_dir("INTERVIEW_RECORD") / "audio").glob("*")) == []
    disk = "".join(p.read_bytes().decode("latin-1") for p in (agent_dir("INTERVIEW_RECORD") / "records").rglob("*.rec"))
    now_ = json.dumps({c: dict(hr.st().load()[c]) for c in ("sessions", "tokens")}, default=str)
    assert "private pad text" not in disk + now_ and tok not in disk + now_
    assert gw.candidate_consent(tok, ["events"], "v1")["status"] == "not_found"
    t = trace_text()
    assert "session.closed" in t and "private pad text" not in t and "secretaudio" not in t


def test_roles_org_and_input_limits(env):
    ats, rec, sess, tok, itok, cid, c = env
    assert rec.list_sessions()["status"] == "unauthenticated"
    with as_(who("interviewer")):
        assert rec.create_session(application_id="x", interviewer_ids=["a"])["status"] == "denied" and rec.evidence_view(session_id=sess)["status"] == "denied"
    with as_(who("recruiter", org="other")):
        assert rec.list_sessions()["sessions"] == [] and rec.close_session(session_id=sess)["status"] == "not_found"
    with as_(c["rec"]):
        app = next(iter(json.loads((agent_dir("ATS_CORE") / "evaluation.json").read_text())["applications"]))
        for bad in ([], ["candidate"], ["a", "a"], "iv-1"):
            assert rec.create_session(application_id=app, interviewer_ids=bad)["status"] == "invalid_input"
        assert rec.create_session(application_id=app, interviewer_ids=["a"], retention_days=0)["status"] == "invalid_input"
        assert rec.create_session(application_id="app-nope", interviewer_ids=["a"])["status"] == "not_found"
        assert rec.issue_participant_token(session_id=sess, participant="stranger")["status"] == "not_found"
        assert rec.issue_participant_token(session_id=sess, hours=500)["status"] == "invalid_input"


def test_staff_actions_on_a_session_need_a_connection_to_it(env):
    ats, rec, sess, tok, itok, cid, c = env
    consent_all(rec, sess, tok)
    gw.ingest_event(tok, "join")
    stranger = who("recruiter", id="rec-other")
    with as_(stranger):
        assert rec.mark_event(session_id=sess, seq=1, mark="relevant", reason="x")["status"] == "denied"
        assert rec.close_session(session_id=sess)["status"] == "denied"
        assert rec.issue_participant_token(session_id=sess)["status"] == "denied"
    with as_(c["mgr"]):
        assert rec.mark_event(session_id=sess, seq=1, mark="relevant", reason="x")["status"] == "ok"


def test_appending_an_event_does_not_read_the_whole_log_and_heals_a_session_record_that_lags(monkeypatch):
    """KAN-64 review: every event decrypted and parsed up to 50,000 lines under the store lock shared by all organisations."""
    from velaris.agentkit import hiring_record as hr
    s = {"id": "s1", "status": "open", "org": "acme", "event_count": 0, "chain_head": hr.GENESIS, "tracks": {},
         "consents": {"candidate": {"scopes": ["events"], "notice_version": "v", "at": 1, "withdrawn_at": None}},
         "retention_until": "2999-01-01"}
    reads = []
    real = hr.read_lines
    monkeypatch.setattr(hr, "read_lines", lambda *a, **k: reads.append(1) or real(*a, **k))
    for i in range(30):
        hr.append_event("acme", s, "candidate", "join", None)
    assert reads == [] and s["event_count"] == 30
    assert hr.verify_chain(real(hr._events_path("s1"), encrypted=hr._SEAL))
    s["event_count"], s["chain_head"] = 29, "x" * 64                  # the session record lags behind the file (crash between the two writes)
    e = hr.append_event("acme", s, "candidate", "join", None)
    assert reads == [1] and e["seq"] == 31 and hr.verify_chain(real(hr._events_path("s1"), encrypted=hr._SEAL))
