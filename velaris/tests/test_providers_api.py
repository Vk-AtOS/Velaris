"""KAN-18 backend: /providers on the Velaris API. model_admin only, keys never come back, test is safe."""
import json
import secrets

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from velaris.api.app import Settings, create_app
from velaris.api.auth import make_assertion, sign
from velaris.intel import catalogue, llm, trace, usage
from velaris.tests.fake_model_server import FakeModelServer, chat_reply

SECRET, KEY = b"s" * 32, Ed25519PrivateKey.generate()
APIKEY = "sk-live-ABCDEFGH-1234567890"


class _Engine:
    router = type("R", (), {"departments": {}, "failed": {}})()

    def list_agents(self):
        return []


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("VELARIS_ORG", "acme")
    return TestClient(create_app(Settings(secret=SECRET, identity_key=KEY.public_key(), org="acme"), engine=_Engine()))


def send(c, method, path, body=None, *, roles=("model_admin",), org="acme"):
    content = b"" if body is None else json.dumps(body).encode()
    nonce = secrets.token_urlsafe(16)
    identity = make_assertion(KEY, sub="u1", org=org, roles=roles, nonce=nonce)
    return c.request(method, path, content=content, headers=sign(SECRET, method, path, content, identity, nonce=nonce))


def test_only_model_admins_may_touch_providers(client):
    for method, path, body in [("GET", "/providers", None), ("POST", "/providers", {"id": "x", "kind": "ollama"}),
                               ("PUT", "/providers/x", {"enabled": False}), ("DELETE", "/providers/x", None),
                               ("POST", "/providers/x/rotate", {"api_key": APIKEY}), ("POST", "/providers/x/test", None),
                               ("GET", "/providers/usage", None), ("GET", "/providers/x/models", None)]:
        for roles in ((), ("hr_admin", "payroll_admin")):
            r = send(client, method, path, body, roles=roles)
            assert r.status_code == 403 and r.json()["error"]["code"] == "access_denied", (method, path)
    assert client.get("/providers").json()["error"]["code"] == "unsigned"


def test_add_list_update_rotate_delete_and_the_key_is_never_returned(client):
    with FakeModelServer() as srv:
        r = send(client, "POST", "/providers", {"id": "gw", "kind": "openai_compatible", "base_url": srv.base_url,
                                                "api_key": APIKEY, "allow_local": True,
                                                "sensitivity_allowed": ["public", "internal"]})
        assert r.status_code == 200 and r.json()["provider"]["key_last4"] == APIKEY[-4:]
        listing = send(client, "GET", "/providers").json()
        assert [p["id"] for p in listing["providers"]] == ["gw"] and "omniroute" in listing["presets"]
        assert APIKEY not in r.text + json.dumps(listing)
        assert send(client, "PUT", "/providers/gw", {"enabled": False}).json()["provider"]["enabled"] is False
        assert send(client, "PUT", "/providers/gw", {"sensitivity_allowed": ["bogus"]}).status_code == 400
        rot = send(client, "POST", "/providers/gw/rotate", {"api_key": "sk-second-KEY-0000-9999"}).json()["provider"]
        assert rot["key_last4"] == "9999"
        srv.reply("/models", {"data": [{"id": "m1"}]})
        send(client, "PUT", "/providers/gw", {"enabled": True})
        assert send(client, "POST", "/providers/gw/test").json()["ok"] is True
        assert send(client, "POST", "/providers/gw/models/refresh").json()["added"] == 1
        assert [m["model"] for m in send(client, "GET", "/providers/gw/models").json()["models"]] == ["m1"]
    assert send(client, "DELETE", "/providers/gw").json() == {"deleted": "gw"}
    assert send(client, "DELETE", "/providers/gw").status_code == 404
    traced = "".join(json.dumps(e) for e in trace.entries())
    assert APIKEY not in traced and "sk-second-KEY" not in traced


def test_test_connection_never_returns_the_providers_own_text(client):
    with FakeModelServer() as srv:
        send(client, "POST", "/providers", {"id": "gw", "kind": "openai_compatible", "base_url": srv.base_url,
                                            "api_key": APIKEY, "allow_local": True})
        srv.reply("/models", {"error": f"invalid key {APIKEY} for host internal.corp"}, status=401)
        r = send(client, "POST", "/providers/gw/test")
        assert r.json()["error"] == "key_rejected" and APIKEY not in r.text and "internal.corp" not in r.text


def test_preset_and_bad_input(client):
    r = send(client, "POST", "/providers", {"id": "omniroute", "preset": "omniroute"})
    assert r.status_code == 200 and r.json()["provider"]["free_pool"] is True
    assert send(client, "POST", "/providers", {"id": "o2", "preset": "omniroute", "sensitivity_allowed": ["restricted"]}).status_code == 400
    for bad in ({"id": "Bad Id", "kind": "ollama"}, {"id": "anthropic", "kind": "ollama"}, {"id": "ok", "kind": "x"}):
        assert send(client, "POST", "/providers", bad).status_code == 400
    assert send(client, "DELETE", "/providers/..%2Fx").status_code in (400, 404)


def test_no_vault_key_is_a_clear_503_and_stores_nothing(client, monkeypatch):
    monkeypatch.delenv("VELARIS_VAULT_KEY")
    r = send(client, "POST", "/providers", {"id": "gw", "kind": "ollama", "api_key": APIKEY})
    assert r.status_code == 503 and r.json()["error"]["code"] == "vault_unavailable"
    assert send(client, "GET", "/providers").json()["providers"] == []


def test_usage_panel_is_scoped_to_the_callers_organisation(client):
    catalogue.configure("gw", "m", price_in_per_mtok=1.0, price_out_per_mtok=1.0)
    with FakeModelServer() as srv:
        send(client, "POST", "/providers", {"id": "gw", "kind": "openai_compatible", "base_url": srv.base_url,
                                            "allow_local": True, "sensitivity_allowed": ["public"]})
        srv.reply("/chat/completions", chat_reply(tokens=(1000, 1000)))
        with usage.usage_context(org="acme"):
            llm.LLM().complete("x", model="gw:m", sensitivity="public")
        with usage.usage_context(org="other"):
            llm.LLM().complete("x", model="gw:m", sensitivity="public")
    out = send(client, "GET", "/providers/usage?days=7").json()
    assert len(out["days"]) == 7 and out["days"][-1]["calls"] == 1 and out["days"][-1]["tokens_in"] == 1000
    assert out["days"][-1]["cost_usd"] == pytest.approx(0.002) and out["month"]["calls"] == 1
    assert send(client, "GET", "/providers/usage?days=x").status_code == 400
