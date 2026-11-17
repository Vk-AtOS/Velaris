"""velaris.api: gateway authentication, caller propagation, the allowlist, approvals, tracing.

Uses FastAPI's TestClient (no listener) and a demo agent dispatched through the real
BackendEngine.run. Prime is a fake behind httpx.MockTransport.
"""
import json
import os
import secrets
import types

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from velaris.api import allowlist
from velaris.api.allowlist import ACT, READ, Rule
from velaris.api.app import Settings, create_app
from velaris.api.auth import make_assertion, sign
from velaris.backend.engine import BackendEngine
from velaris.core.access import authorize_read, current_caller
from velaris.core.prime import PrimeGate
from velaris.intel import trace
from velaris.intel.llm import FakeLLM

SECRET = b"s" * 32
KEY = Ed25519PrivateKey.generate()
BOOKED = []


class DemoAgent:
    """A demo agent for the API tests."""

    def whoami(self):
        c = current_caller()
        return {"id": c.id, "org": c.org, "roles": sorted(c.roles), "employee_id": c.employee_id}

    def payslip(self, employee_id):
        authorize_read("pay", employee_id, agent="DEMO")
        return {"employee_id": employee_id, "net": 100}

    def book(self, room, by):
        """Book a room."""
        BOOKED.append((room, by, current_caller().id))
        return {"booked": room}

    def remember(self, text, scope):
        return {"kept": text}

    def wipe(self):
        BOOKED.append("wiped")

    def _private(self):
        BOOKED.append("private")


class Router:
    departments, failed = {"DEMO": "test"}, {"BROKEN": "ImportError: x"}

    def __init__(self):
        self.module = types.ModuleType("velaris_api_test_demo")
        DemoAgent.__module__ = self.module.__name__
        self.module.DemoAgent = DemoAgent

    def list_agents(self):
        return ["DEMO"]

    def get_agent(self, name):
        return self.module if name == "DEMO" else None


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    monkeypatch.setitem(allowlist.METHODS, "DEMO", {
        "whoami": Rule(READ), "payslip": Rule(READ), "book": Rule(ACT, actor="by"),
        "remember": Rule(READ, scope="scope"), "_private": Rule(READ)})
    BOOKED.clear()


def engine():
    e = BackendEngine.__new__(BackendEngine)
    e.router = Router()
    return e


def app_client(tmp_path, gate=None, llm=None):
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), gate=gate, flow_db=str(tmp_path / "flow.db"),
                        org="acme", llm=llm or FakeLLM(lambda p, m: pytest.fail("no model expected")))
    return TestClient(create_app(settings, engine=engine()))


def send(client, method, path, body=None, *, sub="u1", org="acme", roles=(), employee_id=None, raw=None,
         secret=SECRET, key=KEY, ts=None, identity=None, nonce=None, headers=None):
    content = raw if raw is not None else (b"" if body is None else json.dumps(body).encode())
    nonce = nonce or secrets.token_urlsafe(16)
    if identity is None:
        identity = make_assertion(key, sub=sub, org=org, roles=roles, employee_id=employee_id, nonce=nonce)
    h = headers or sign(secret, method, path, content, identity, nonce=nonce, ts=ts)
    return client.request(method, path, content=content, headers=h)


def api_entries(action):
    return [e["payload"] for e in trace.entries() if e["actor"] == "api" and e["action"] == action]


def test_service_authentication(tmp_path):
    c = app_client(tmp_path)
    assert c.get("/health").json() == {"status": "ok"}
    assert c.get("/agents").json()["error"]["code"] == "unsigned"
    assert c.get("/agents", headers={"X-Caller-Id": "admin", "X-Caller-Org": "acme"}).status_code == 401
    assert send(c, "GET", "/agents", secret=b"x" * 32).json()["error"]["code"] == "bad_signature"
    assert send(c, "GET", "/agents", ts=1).json()["error"]["code"] == "stale"
    assert send(c, "GET", "/agents", identity="").json()["error"]["code"] == "no_identity"
    assert send(c, "GET", "/agents", key=Ed25519PrivateKey.generate()).json()["error"]["code"] == "bad_identity"
    other = make_assertion(KEY, sub="u1", org="acme", nonce="another-request-nonce")
    assert send(c, "GET", "/agents", identity=other).json()["error"]["code"] == "bad_identity"
    expired = make_assertion(KEY, sub="u1", org="acme", nonce="n" * 16, now=1000)
    assert send(c, "GET", "/agents", identity=expired, nonce="n" * 16).json()["error"]["code"] == "bad_identity"
    assert send(c, "GET", "/agents", sub="").json()["error"]["code"] == "bad_identity"
    # a body changed after signing does not verify
    nonce = secrets.token_urlsafe(16)
    h = sign(SECRET, "POST", "/agents/DEMO/whoami", b"{}", make_assertion(KEY, sub="u1", org="acme", nonce=nonce),
             nonce=nonce)
    assert c.post("/agents/DEMO/whoami", content=b'{"x":1}', headers=h).json()["error"]["code"] == "bad_signature"
    # the same signed request twice: the second is a replay
    nonce = secrets.token_urlsafe(16)
    h = sign(SECRET, "GET", "/agents", b"", make_assertion(KEY, sub="u1", org="acme", nonce=nonce), nonce=nonce)
    assert c.get("/agents", headers=h).status_code == 200
    assert c.get("/agents", headers=h).json()["error"]["code"] == "replay"
    big = send(c, "POST", "/agents/DEMO/whoami", raw=b"{" + b" " * (65 * 1024) + b"}")
    assert big.status_code == 413 and big.json()["error"]["code"] == "too_large"


def test_caller_reaches_the_agent_and_every_call_is_traced(tmp_path):
    c = app_client(tmp_path)
    r = send(c, "POST", "/agents/DEMO/whoami", {}, sub="u7", roles=["hr_admin"], employee_id="E7")
    assert r.status_code == 200
    assert r.json()["result"] == {"id": "u7", "org": "acme", "roles": ["hr_admin"], "employee_id": "E7"}
    assert current_caller() is None                                      # nothing leaks out of the call
    ok = send(c, "POST", "/agents/DEMO/payslip", {"employee_id": "E7"}, sub="u7", employee_id="E7")
    assert ok.json()["result"]["net"] == 100
    denied = send(c, "POST", "/agents/DEMO/payslip", {"employee_id": "E8"}, sub="u7", employee_id="E7")
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "access_denied"
    results = api_entries("agent.result")
    assert [(p["caller"], p["method"], p["outcome"]) for p in results] == [
        ("u7", "whoami", "ok"), ("u7", "payslip", "ok"), ("u7", "payslip", "denied")]
    assert any(e["action"] == "sensitive_read.denied" and e["payload"]["caller"] == "u7" for e in trace.entries())
    assert send(c, "GET", "/trace/verify", roles=["governance_admin"]).json()["ok"] is True


def test_allowlist_private_and_parameters(tmp_path):
    c = app_client(tmp_path)
    assert send(c, "POST", "/agents/DEMO/wipe", {}).json()["error"]["code"] == "not_allowed"
    assert send(c, "POST", "/agents/DEMO/_private", {}).json()["error"]["code"] == "not_allowed"  # even if declared
    assert send(c, "POST", "/agents/NOPE/whoami", {}).json()["error"]["code"] == "not_allowed"
    assert send(c, "POST", "/agents/DEMO/whoami", {"caller": {"id": "boss"}}).json()["error"]["code"] == "bad_params"
    assert send(c, "POST", "/agents/DEMO/payslip", {}).json()["error"]["code"] == "bad_params"
    assert send(c, "POST", "/agents/DEMO/whoami", [1]).json()["error"]["code"] == "bad_params"
    assert send(c, "POST", "/agents/DEMO/remember", {"text": "x", "scope": "other:hr"}).status_code == 403
    assert send(c, "POST", "/agents/DEMO/remember", {"text": "x", "scope": "acme:hr"}).status_code == 403          # KAN-69 SV2-08: not a listed kind
    for ok in ("acme", "acme:user:u1"):
        assert send(c, "POST", "/agents/DEMO/remember", {"text": "x", "scope": ok}).status_code == 200
    assert send(c, "POST", "/agents/DEMO/remember", {"text": "x", "scope": "acme:user:u2"}).status_code == 403      # another member's scope
    os.environ["VELARIS_SHARED_SCOPE_KINDS"] = "team"
    try:
        assert send(c, "POST", "/agents/DEMO/remember", {"text": "x", "scope": "acme:team:hr"}).status_code == 200
        assert send(c, "POST", "/agents/DEMO/remember", {"text": "x", "scope": "acme:user:u2"}).status_code == 403
    finally:
        del os.environ["VELARIS_SHARED_SCOPE_KINDS"]
    assert BOOKED == []
    assert [p["outcome"] for p in api_entries("agent.call")][:3] == ["not_allowed"] * 3
    listing = send(c, "GET", "/agents").json()
    demo = listing["agents"][0]
    assert demo["name"] == "DEMO" and demo["department"] == "test" and demo["summary"].startswith("A demo agent")
    methods = {m["name"]: m for m in demo["methods"]}
    assert "_private" not in methods and methods["wipe"]["http"] is None and methods["book"]["http"] == ACT
    assert methods["book"]["signature"] == "(room, by)" and listing["failed"] == ["BROKEN"]


def test_consequential_call_waits_for_a_second_person(tmp_path):
    c = app_client(tmp_path)
    assert send(c, "POST", "/agents/DEMO/book", {"room": "A", "by": "boss"}).status_code == 403
    r = send(c, "POST", "/agents/DEMO/book", {"room": "A"})
    assert r.status_code == 202 and r.json()["approval"] == "local"
    run = r.json()["run"]
    assert run["status"] == "waiting_approval" and run["pending"]["args"] == {"room": "A"} and BOOKED == []
    run_id, h = run["run_id"], run["pending"]["call_hash"]
    assert send(c, "GET", "/flows/pending").json()["runs"][0]["run_id"] == run_id
    assert send(c, "GET", f"/flows/{run_id}", sub="u2").status_code == 404           # not theirs
    assert send(c, "GET", "/flows/pending", sub="u2").json()["runs"] == []
    own = send(c, "POST", f"/flows/{run_id}/decide", {"call_hash": h, "approve": True})
    assert own.json()["error"]["code"] == "four_eyes"
    assert send(c, "POST", f"/flows/{run_id}/decide", {"call_hash": h, "approve": True}, sub="u3",
                org="globex", roles=["flow_approver"]).status_code == 403    # not this deployment's org
    wrong = send(c, "POST", f"/flows/{run_id}/decide", {"call_hash": "0" * 64, "approve": True}, sub="u2",
                 roles=["flow_approver"])
    assert wrong.status_code == 409 and BOOKED == []
    done = send(c, "POST", f"/flows/{run_id}/decide", {"call_hash": h, "approve": True}, sub="u2",
                roles=["flow_approver"])
    assert done.json()["status"] == "done" and BOOKED == [("A", "u1", "u1")]       # runs as the person it is for
    assert send(c, "GET", f"/flows/{run_id}/verify").json()["ok"] is True
    assert [p["outcome"] for p in api_entries("agent.call")] == ["denied", "approval_requested"]


def test_model_flow_uses_only_declared_tools(tmp_path):
    replies = iter([json.dumps({"tool": "DEMO.book", "args": {"room": "B"}})])
    c = app_client(tmp_path, llm=FakeLLM(lambda p, m: next(replies)))
    assert send(c, "POST", "/flows", {"task": "x", "tools": ["DEMO.wipe"]}).status_code == 403
    assert send(c, "POST", "/flows", {"task": "", "tools": []}).status_code == 400
    r = send(c, "POST", "/flows", {"task": "book room B", "tools": ["DEMO.book", "DEMO.whoami"]}).json()
    assert r["status"] == "waiting_approval" and r["pending"]["tool"] == "DEMO.book" and BOOKED == []


class FakePrime:
    def __init__(self):
        self.req = None

    def handler(self, request):
        if request.method == "POST":
            body = json.loads(request.content)
            self.req = {"id": "r1", "state": "pending", "request_hash": "a" * 64, "executor": body["executor"],
                        "action": {"type": body["type"], "on_behalf_of": body["on_behalf_of"],
                                   "params": body["params"]}, "decided_by": None, "execution": None}
            return httpx.Response(201, json={"outcome": "NEEDS_APPROVAL", "reason": "", "request": self.req})
        return httpx.Response(200, json=self.req)


def test_with_prime_the_approval_comes_from_prime_only(tmp_path):
    fake = FakePrime()
    c = app_client(tmp_path, gate=PrimeGate("http://aetheros.test", "aesk_x", transport=httpx.MockTransport(fake.handler)))
    r = send(c, "POST", "/agents/DEMO/book", {"room": "C"}).json()
    assert r["approval"] == "prime" and r["run"]["pending"]["approver"]["prime_request_id"] == "r1"
    assert fake.req["action"]["on_behalf_of"] == "u1"
    assert fake.req["action"]["params"]["call_hash"] == r["run"]["pending"]["call_hash"]
    run_id = r["run"]["run_id"]
    blocked = send(c, "POST", f"/flows/{run_id}/decide", {"call_hash": fake.req["action"]["params"]["call_hash"],
                                                          "approve": True}, sub="u2", roles=["flow_approver"])
    assert blocked.json()["error"]["code"] == "decided_in_prime" and BOOKED == []
    assert send(c, "GET", f"/flows/{run_id}").json()["status"] == "waiting_approval"
    fake.req.update(state="approved", decided_by="u2", execution={"status": "succeeded"})
    assert send(c, "GET", f"/flows/{run_id}").json()["status"] == "done" and BOOKED == [("C", "u1", "u1")]


def test_deployment_serves_one_organisation(tmp_path, monkeypatch):
    c = app_client(tmp_path)
    r = send(c, "POST", "/agents/DEMO/whoami", {}, org="globex")
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_organisation"
    assert send(c, "GET", "/agents", org="globex").status_code == 403           # every endpoint, before dispatch
    assert [p["outcome"] for p in api_entries("request.refused")] == ["org_mismatch"] * 2
    assert api_entries("agent.call") == []
    # no organisation configured: the app and from_env refuse to start
    with pytest.raises(ValueError):
        create_app(Settings(secret=SECRET, identity_key=KEY.public_key()), engine=engine())
    for k, v in (("VELARIS_API_SECRET", "s" * 32), ("VELARIS_IDENTITY_PUBLIC_KEY", str(tmp_path / "k.pem"))):
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("VELARIS_ORG", raising=False)
    with pytest.raises(ValueError, match="VELARIS_ORG"):
        Settings.from_env()


def test_owner_moving_a_run_loses_roles_revoked_since_it_started(tmp_path, monkeypatch):
    """KAN-108: a run's owner roles were frozen at start; now the owner's current roles cap what the run can do."""
    seen = []
    monkeypatch.setattr(DemoAgent, "act_roles", lambda self, room: seen.append(sorted(current_caller().roles)) or {"ok": 1}, raising=False)
    monkeypatch.setitem(allowlist.METHODS["DEMO"], "act_roles", Rule(ACT))
    fake = FakePrime()
    c = app_client(tmp_path, gate=PrimeGate("http://aetheros.test", "aesk_x", transport=httpx.MockTransport(fake.handler)))
    r = send(c, "POST", "/agents/DEMO/act_roles", {"room": "C"}, roles=["hr_admin"]).json()
    run_id = r["run"]["run_id"]
    fake.req.update(state="approved", decided_by="u2", execution={"status": "succeeded"})
    assert send(c, "GET", f"/flows/{run_id}", roles=[]).json()["status"] == "done"      # u1 is no longer hr_admin
    assert seen == [[]]


def test_identity_public_key_can_come_from_the_environment_as_pem(monkeypatch, tmp_path):
    """Container platforms inject env, not files: VELARIS_IDENTITY_PUBLIC_KEY_PEM holds the key itself (KAN-112)."""
    from cryptography.hazmat.primitives import serialization
    pem = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setenv("VELARIS_API_SECRET", "s" * 32)
    monkeypatch.setenv("VELARIS_ORG", "acme")
    monkeypatch.delenv("VELARIS_IDENTITY_PUBLIC_KEY", raising=False)
    monkeypatch.setenv("VELARIS_IDENTITY_PUBLIC_KEY_PEM", pem.decode())
    s = Settings.from_env()
    assert s.identity_key.public_bytes_raw() == KEY.public_key().public_bytes_raw()
    monkeypatch.delenv("VELARIS_IDENTITY_PUBLIC_KEY_PEM")
    with pytest.raises(ValueError, match="VELARIS_IDENTITY_PUBLIC_KEY"):
        Settings.from_env()                                                   # neither: refuses to start
