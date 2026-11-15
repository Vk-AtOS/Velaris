"""KAN-120: /metrics (signed + role), the internal listener, request ids, JSON logs with tokens masked."""
import io
import json
import logging
import urllib.error
import urllib.request

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from velaris.api import observability as obs
from velaris.intel.llm import FakeLLM
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


def test_counters_are_shared_between_workers_and_spend_uses_the_price_table(monkeypatch):
    """KAN-120: per-process counters gave each worker its own totals; chat's own model was not counted; spend was only characters."""
    import json as _json
    monkeypatch.setenv("VELARIS_LLM_PRICES", _json.dumps({"fake:model": {"in": 3.0, "out": 15.0}}))
    w1, w2 = obs.Metrics(), obs.Metrics()                                    # two worker processes sharing VELARIS_DATA
    llm = obs.CountingLLM(FakeLLM(lambda p, m: "y" * 400), w1)
    llm.complete("x" * 4000, model="fake:model")
    obs.CountingLLM(FakeLLM(lambda p, m: "z"), w2).complete("hello", model="other:model")           # no price for this one
    w2.inc("velaris_calls_total", action="agents.list", outcome="ok")
    w1.flush()
    w2.flush()                                                               # (a worker flushes at least once a second on its own)
    for text in (w1.render(), w2.render()):                                  # the same answer whichever worker is scraped
        assert 'velaris_llm_calls_total{model="fake:model"} 1' in text and 'velaris_llm_calls_total{model="other:model"} 1' in text
        assert 'velaris_llm_unpriced_calls_total{model="other:model"} 1' in text
        assert 'velaris_calls_total{action="agents.list",outcome="ok"} 1' in text
        spend = [float(l.split()[-1]) for l in text.splitlines() if l.startswith('velaris_llm_spend_usd_total{model="fake:model"}')][0]
        assert abs(spend - (1000 * 3.0 + 100 * 15.0) / 1e6) < 1e-9
    w1.in_flight, w2.in_flight = 2, 3
    w2.flush()
    assert "velaris_queue_depth 5" in w1.render()                          # the gauge sums the live workers


def test_the_chat_assistant_model_is_counted_too(tmp_path, monkeypatch):
    from velaris.api.app import Settings, create_app
    from velaris.chat import api as chat_api
    seen = {}
    real = chat_api.chat_router
    monkeypatch.setattr("velaris.api.app.chat_router", lambda *a, **k: (seen.update(k), real(*a, **k))[1])
    settings = Settings(secret=b"s" * 32, identity_key=Ed25519PrivateKey.generate().public_key(), org="acme", llm=FakeLLM(lambda p, m: "hi"))
    create_app(settings, engine=object())
    assert isinstance(seen["llm"], obs.CountingLLM)
