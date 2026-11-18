"""KAN-93: connectors (host allow-list, redirects, errors), communications, data_knowledge, executive."""
import io
import json
import os
import random
import urllib.error
from datetime import date, timedelta
from importlib import import_module

import pytest

from velaris.core.access import Caller, acting_as


def mod(name):
    return import_module(f"velaris.agents.{name}.main")


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def zoho(monkeypatch, replies):
    """A connector whose network layer replays `replies` (dicts, or an HTTP status int) and records requests."""
    M = mod("ZOHO_CONNECTOR")
    z = M.ZohoConnector({"client_id": "i", "client_secret": "s", "refresh_token": "r"})
    sent = []

    def fake_open(req, timeout=None):
        sent.append((req.full_url, dict(req.header_items()), timeout))
        r = replies.pop(0)
        if isinstance(r, int):
            raise urllib.error.HTTPError(req.full_url, r, "x", {}, None)
        return Resp(json.dumps(r).encode())
    monkeypatch.setattr(M._OPENER, "open", fake_open)
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    return M, z, sent


@pytest.mark.parametrize("url", ["https://evil.example/x", "http://projectsapi.zoho.in/x", "https://zoho.in.evil.com/x",
                                 "https://projectsapi.zoho.com/x", "https://user:p@projectsapi.zoho.in/x", "ftp://a.zoho.in/x",
                                 "https://projectsapi.zoho.in.evil.com/", None, 5])
def test_the_token_is_never_sent_to_another_host(monkeypatch, url):
    M, z, sent = zoho(monkeypatch, [{"access_token": "T", "expires_in": 3600}, {"ok": 1}])
    with pytest.raises(M.ZohoError):
        z.get(url)
    with pytest.raises(M.ZohoError):
        z.post(url, {})
    assert sent == []                                        # not even the token refresh happened


def test_zoho_calls_retry_then_fail_without_leaking_the_token(monkeypatch):
    M, z, sent = zoho(monkeypatch, [{"access_token": "TOKEN-123", "expires_in": 3600}, 503, {"v": 1}])
    assert z.get("https://projectsapi.zoho.in/restapi/portal/p/projects/") == {"v": 1}      # 503 once, then fine
    assert all(t == 30 or t == 15 for _, _, t in sent) and len(sent) == 3
    M, z, sent = zoho(monkeypatch, [{"access_token": "TOKEN-123", "expires_in": 3600}, 404])
    with pytest.raises(M.ZohoError) as e:
        z.get("https://projectsapi.zoho.in/x")
    assert e.value.status == 404 and "TOKEN-123" not in str(e.value) and len(sent) == 2     # 404 is not retried
    M, z, sent = zoho(monkeypatch, [{"access_token": "T", "expires_in": 3600}, 500, 500, 500])
    with pytest.raises(M.ZohoError):
        z.get("https://projectsapi.zoho.in/x")


def test_redirects_are_not_followed():
    M = mod("ZOHO_CONNECTOR")
    handler = M._NoRedirect()
    import urllib.request
    assert handler.redirect_request(urllib.request.Request("https://a.zoho.in/"), None, 302, "x", {}, "https://evil/") is None


def test_payroll_statutory_names_match_whole_words_and_health_reports_config(monkeypatch):
    cls = next(v for k, v in vars(mod("ZOHO_PAYROLL")).items() if isinstance(v, type) and hasattr(v, "get_statutory_deductions"))
    p = cls({})
    assert p.health_check()["status"] == "unconfigured"
    monkeypatch.setattr(p, "_payslip", lambda *a: {"deductions": [
        {"name": "EPF", "amount": 1}, {"name": "Professional Tax", "amount": 2}, {"name": "PT", "amount": 3},
        {"name": "Optional Bonus Recovery", "amount": 9}, {"name": "SPF refund", "amount": 8}, {"name": "ESI", "amount": 4}]})
    monkeypatch.setattr(p, "_allow", lambda *a, **k: None)
    got = p.get_statutory_deductions("E1", 2026, 4)["statutory"]
    assert got == {"EPF": 1, "Professional Tax": 2, "PT": 3, "ESI": 4}


def test_zoho_projects_needs_no_config_and_counts_late_closed_tasks(monkeypatch):
    cls = next(v for k, v in vars(mod("ZOHO_PROJECTS")).items() if isinstance(v, type) and hasattr(v, "get_task_summary"))
    zp = cls()                                               # was AttributeError: NoneType has no attribute 'get'
    assert zp.health_check()["status"] == "unconfigured"
    done = {"status": {"name": "Closed"}}
    monkeypatch.setattr(zp, "get_tasks_by_owner", lambda *a: [
        {**done, "end_date_long": 100, "completed_time_long": 90}, {**done, "end_date_long": 100, "completed_time_long": 500}])
    s = zp.get_task_summary("p", "o")
    assert s["late_closed"] == 1 and s["on_time_rate"] == 50.0


def test_action_items_with_relative_dates_do_not_crash_and_overdue_ignores_text_hints():
    X = mod("ACTION_ITEM_EXTRACTOR")
    a = next(v for k, v in vars(X).items() if isinstance(v, type) and hasattr(v, "get_overdue"))()
    assert X._extract_due_hint("send the report tomorrow") == (date.today() + timedelta(days=1)).isoformat()
    assert X._extract_due_hint("finish by oct 15") == "oct 15"
    conn = X._db()
    cols = [r[1] for r in conn.execute("PRAGMA table_info(action_items)")]
    base = {c: None for c in cols}
    for due, text in (("2000-01-01", "old"), ("oct 15", "hint"), ((date.today() + timedelta(days=9)).isoformat(), "future")):
        row = {**base, "text": text, "due_date": due, "status": "open", "created_on": "2026-01-01"}
        use = {k: v for k, v in row.items() if k != "id" and v is not None}
        conn.execute(f"INSERT INTO action_items ({','.join(use)}) VALUES ({','.join('?' * len(use))})", list(use.values()))
    conn.commit()
    conn.close()
    assert [r["text"] for r in a.get_overdue()] == ["old"]


def test_call_recorder_needs_consent_a_caller_and_never_puts_the_raw_id_in_a_name(monkeypatch, tmp_path):
    R = mod("CALL_RECORDER")
    started = []
    monkeypatch.setattr(R.subprocess, "Popen", lambda cmd, **k: started.append(cmd) or type("P", (), {"poll": lambda s: 0})())
    rec = R.CallRecorder({"recordings_dir": str(tmp_path / "rec")})
    assert rec.start("c1", consent=True)["error"] == "unauthenticated"
    with acting_as(Caller("u", "kf")):
        assert rec.start("c1")["error"] == "consent_required" and started == []
        out = rec.start("../../x", consent=True)
    assert "/../" not in out["filepath"] and os.path.dirname(out["filepath"]) == str(tmp_path / "rec")
    monkeypatch.setattr(R.subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(FileNotFoundError("ffmpeg")))
    assert rec.health_check()["status"] == "degraded"       # was an uncaught FileNotFoundError


def test_call_transcriber_reads_only_audio_under_its_folders(tmp_path, monkeypatch):
    T = mod("CALL_TRANSCRIBER").CallTranscriber
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF")
    secret = tmp_path / "notes.txt"
    secret.write_text("secret")
    t = T({"audio_roots": [str(tmp_path)]})
    monkeypatch.setattr(t, "_load_model", lambda: (_ for _ in ()).throw(RuntimeError("no model")))
    assert t.transcribe(str(audio))["error"] == "unauthenticated"
    with acting_as(Caller("u", "kf")):
        assert "audio file" in t.transcribe(str(secret))["error"]
        assert "outside" in T().transcribe(str(audio))["error"]                 # no audio_roots configured for this one
        assert "outside" in t.transcribe("/etc/passwd.wav")["error"]
        link = tmp_path / "link.wav"
        link.symlink_to("/etc/hosts")
        assert "outside" in t.transcribe(str(link))["error"]                    # a symlink out of the folder
        assert t.transcribe(str(audio))["error"] == "no model"                  # allowed path reaches the model
        with pytest.raises(RuntimeError):
            t.transcribe_to_text(str(audio))                                    # an error is not a transcript


def test_temporal_snapshots_use_the_newest_label_and_unknown_labels_are_not_equal():
    S = mod("TEMPORAL_SNAPSHOTS").TemporalSnapshots
    s = S()
    s.create_snapshot("v", 1)
    s.create_snapshot("v", 2)
    s.create_snapshot("w", 2)
    assert s.restore("v") == 2 and s.compare("v", "w")["equal"] is True        # restore and compare agree: newest
    assert s.compare("nope", "nada")["equal"] is None and s.compare("v", "nada")["found"] == {"a": True, "b": False}
    assert S().list_snapshots() == ["v", "v", "w"] and oct(os.stat(s.SNAP_PATH).st_mode & 0o777) == "0o600"


def test_oracle_seed_does_not_touch_the_global_generator():
    random.seed(99)
    want = random.random()
    random.seed(99)
    O = mod("ORACLE").OracleAgent
    a, b = O({"seed": 5}), O({"seed": 5})
    assert a.forecast({"x": 0.1}, 200) == b.forecast({"x": 0.1}, 200)
    assert random.random() == want
    assert a.forecast({"x": 0.1}, 10 ** 9)["trials"] == 1_000_000


def test_drift_baseline_is_written_atomically_and_privately():
    D = mod("MEMORY_DRIFT_DETECTOR")
    d = next(v for k, v in vars(D).items() if isinstance(v, type) and hasattr(v, "set_baseline"))()
    d.set_baseline("a", {"x": 1})
    assert oct(os.stat(d.BASELINE_PATH).st_mode & 0o777) == "0o600"
    assert json.loads(open(d.BASELINE_PATH).read()) == {"a": {"x": 1}}
