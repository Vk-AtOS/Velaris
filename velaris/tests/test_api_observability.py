"""KAN-120: /metrics (signed + role), the internal listener, request ids, JSON logs with tokens masked."""
import io
import json
import logging
import urllib.error
import urllib.request

import pytest

from velaris.api import observability as obs
from velaris.tests.test_api_service import app_client, send


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_metrics_need_a_signature_and_the_ops_role(tmp_path):
    c = app_client(tmp_path)
    assert c.get("/metrics").status_code == 401                              # unsigned
    assert send(c, "GET", "/metrics", roles=["hr_admin"]).status_code == 403   # signed, wrong role
    r = send(c, "GET", "/metrics", roles=["ops"])
    assert r.status_code == 200 and "velaris_queue_depth" in r.text and "velaris_approvals_waiting 0" in r.text


def test_counts_refusals_and_trace_failures(tmp_path, monkeypatch):
    c = app_client(tmp_path)
    send(c, "POST", "/agents/NOPE/x", {})                                    # not allowed -> a refusal outcome
    send(c, "GET", "/agents", roles=[])                                       # ok call
    from velaris.intel import trace
    monkeypatch.setattr(trace, "append", lambda *a, **k: (_ for _ in ()).throw(OSError("disk")))
    assert send(c, "GET", "/agents").status_code == 503
    text = c.app.state.metrics.render()
    assert 'velaris_calls_total{action="agent.call",outcome="not_allowed"}' in text
    assert 'velaris_refusals_total{action="agent.call",outcome="not_allowed"}' in text
    assert 'velaris_calls_total{action="agents.list",outcome="ok"} 2' in text
    assert "velaris_trace_failures_total 1" in text


def test_llm_counters():
    m = obs.Metrics()

    class Out:
        text = "hello"

    class Inner:
        def complete(self, prompt, **kw):
            return Out()
    obs.CountingLLM(Inner(), m).complete("abc", model="x:y")
    t = m.render()
    assert 'velaris_llm_calls_total{model="x:y"} 1' in t and 'velaris_llm_prompt_chars_total{model="x:y"} 3' in t
    assert 'velaris_llm_output_chars_total{model="x:y"} 5' in t


def test_request_id_is_echoed_or_generated(tmp_path):
    c = app_client(tmp_path)
    assert c.get("/health", headers={"X-Request-Id": "abcdef123456"}).headers["x-request-id"] == "abcdef123456"
    generated = c.get("/health", headers={"X-Request-Id": "bad id!"}).headers["x-request-id"]
    assert len(generated) == 16 and generated != "bad id!"


def test_logs_are_json_with_request_id_and_masked_tokens():
    buf = io.StringIO()
    h = logging.StreamHandler(buf)
    h.setFormatter(obs.JsonFormatter())
    log = logging.getLogger("velaris.test_obs")
    log.addHandler(h)
    log.setLevel(logging.INFO)
    tok = "A" * 10 + "SECRETLINKTOKEN" + "z" * 15
    try:
        obs._request_id.set("rid-1")
        log.info("GET /sign/%s/open token=hunter2 ok", tok)
    finally:
        log.removeHandler(h)
    line = json.loads(buf.getvalue())
    assert line["request_id"] == "rid-1" and tok not in buf.getvalue() and "hunter2" not in buf.getvalue()
    assert "/sign/AAAA***/open" in line["msg"]


def test_internal_listener_serves_only_metrics():
    m = obs.Metrics()
    m.inc("velaris_trace_failures_total")
    s = obs.serve_internal(m, lambda: {"velaris_approvals_waiting": 3}, "127.0.0.1", 0)
    try:
        base = f"http://127.0.0.1:{s.server_address[1]}"
        body = urllib.request.urlopen(base + "/metrics", timeout=5).read().decode()
        assert "velaris_approvals_waiting 3" in body and "velaris_trace_failures_total 1" in body
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/agents", timeout=5)
        assert e.value.code == 404
    finally:
        s.shutdown()


def test_aetheros_trace_id_becomes_the_request_id_and_reaches_the_trace(tmp_path):
    import secrets as _s
    from velaris.tests.test_api_service import KEY, SECRET, api_entries, make_assertion, sign
    c = app_client(tmp_path)

    def signed_get(trace_id):
        nonce = _s.token_urlsafe(16)
        h = sign(SECRET, "GET", "/agents", b"", make_assertion(KEY, sub="u1", org="acme", roles=(), employee_id=None,
                                                                  nonce=nonce), nonce=nonce)
        return c.get("/agents", headers={**h, "X-Trace-Id": trace_id})

    r = signed_get("aeth-trace-0123456789abcdef")
    assert r.headers["x-request-id"] == "aeth-trace-0123456789abcdef"
    assert api_entries("agents.list")[-1]["request_id"] == "aeth-trace-0123456789abcdef"   # the signed trace names it
    hostile = signed_get("x injected id").headers["x-request-id"]
    assert hostile != "x injected id" and len(hostile) == 16
