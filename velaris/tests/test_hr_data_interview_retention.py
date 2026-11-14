"""KAN-107: INTERVIEW_RECORD retention_until is enforced (reads refused, no new events, purge erases)."""
import pytest

from velaris.agentkit import hiring_record as hr
from velaris.agentkit import hiring_record_gateway as gw
from velaris.agentkit.hiring_testkit import as_, trace_text
from velaris.tests.test_hiring_record import consent_all, env  # noqa: F401  (fixture)


def _later(monkeypatch, days):
    real = hr.now
    monkeypatch.setattr(hr, "now", lambda: real() + days * 86400)


def test_expired_session_is_unreadable_takes_no_events_and_purge_erases_it(env, monkeypatch):  # noqa: F811
    ats, rec, sess, tok, itok, cid, c = env
    consent_all(rec, sess, tok)
    gw.ingest_event(tok, "pad_op", {"op": "insert", "pos": 0, "text": "private pad text"})
    with as_(c["adm"]):
        assert "timeline" in rec.evidence_view(session_id=sess)
    _later(monkeypatch, 120)                                    # default retention is 90 days
    assert gw.ingest_event(tok, "join")["status"] == "denied"
    with as_(c["adm"]):
        assert rec.evidence_view(session_id=sess)["status"] == "retention_expired"
        assert rec.replay_pad(session_id=sess)["status"] == "retention_expired"
        with as_(c["rec"]):
            assert rec.purge_expired_sessions()["status"] == "denied"      # recruiter is not an HR admin
        out = rec.purge_expired_sessions()
        assert out["erased_sessions"] == [sess]
        assert rec.list_sessions()["sessions"][0]["status"] == "erased"
    assert hr.events_of(sess) == [] and "retention.purged" in trace_text()


def test_live_session_is_not_purged(env):  # noqa: F811
    ats, rec, sess, tok, itok, cid, c = env
    with as_(c["adm"]):
        assert rec.purge_expired_sessions()["erased_sessions"] == []
