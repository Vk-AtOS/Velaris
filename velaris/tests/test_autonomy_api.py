"""VEL-14: /autonomy on the Velaris API. governance_admin only, validated, traced, persisted."""
import json
import secrets

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from velaris.api.app import Settings, create_app
from velaris.api.auth import make_assertion, sign
from velaris.intel import trace
from velaris.orchestration import autonomy

SECRET, KEY = b"s" * 32, Ed25519PrivateKey.generate()


class _Engine:
    router = type("R", (), {"departments": {}, "failed": {}})()

    def list_agents(self):
        return []


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("VELARIS_ORG", "acme")
    return TestClient(create_app(Settings(secret=SECRET, identity_key=KEY.public_key(), org="acme"), engine=_Engine()))


def send(c, method, path, body=None, *, roles=("governance_admin",)):
    content = b"" if body is None else json.dumps(body).encode()
    nonce = secrets.token_urlsafe(16)
    token = make_assertion(KEY, sub="u1", org="acme", roles=roles, nonce=nonce)
    return c.request(method, path, content=content, headers=sign(SECRET, method, path, content, token, nonce=nonce))


def test_admin_reads_and_changes_the_table_and_it_persists(client):
    t = send(client, "GET", "/autonomy").json()
    assert t["modes"]["internal_write"] == "auto_notify" and t["allowed_modes"] == list(autonomy.MODES)
    assert "irreversible" in t["locked"] and t["money_limit"] == 0.0
    r = send(client, "PUT", "/autonomy/internal_write", {"mode": "approval"})
    assert r.status_code == 200 and r.json()["mode"] == "approval"
    assert autonomy.mode_of("internal_write") == "approval"                              # stored, read back from disk
    assert send(client, "GET", "/autonomy").json()["modes"]["internal_write"] == "approval"


def test_non_admins_get_403_and_nothing_changes(client):
    for roles in ((), ("model_admin", "hr_admin", "security_admin")):
        assert send(client, "GET", "/autonomy", roles=roles).status_code == 403
        r = send(client, "PUT", "/autonomy/read", {"mode": "forbidden"}, roles=roles)
        assert r.status_code == 403 and r.json()["error"]["code"] == "access_denied"
    assert autonomy.mode_of("read") == "auto"
    assert client.get("/autonomy").json()["error"]["code"] == "unsigned"


@pytest.mark.parametrize("path,body", [("/autonomy/read", {"mode": "yolo"}), ("/autonomy/read", {}), ("/autonomy/read", {"mode": 3}),
                                       ("/autonomy/nonsense", {"mode": "auto"}), ("/autonomy/irreversible", {"mode": "auto"}),
                                       ("/autonomy/money_over_limit", {"mode": "auto_notify"})])
def test_invalid_class_mode_or_loosening_a_locked_class_is_400(client, path, body):
    r = send(client, "PUT", path, body)
    assert r.status_code == 400
    assert autonomy.table()["modes"] == autonomy.DEFAULT_MODES


def test_a_change_is_written_to_the_audit_trace(client):
    send(client, "PUT", "/autonomy/unclassified", {"mode": "forbidden"})
    rows = [e for e in trace.entries() if e["action"] in ("mode.set", "autonomy.set")]
    assert {"mode.set", "autonomy.set"} <= {e["action"] for e in rows}
    chg = next(e for e in rows if e["action"] == "mode.set")["payload"]
    assert chg == {"class": "unclassified", "mode": "forbidden", "by": "u1"}
    api = next(e for e in rows if e["action"] == "autonomy.set")["payload"]
    assert api["caller"] == "u1" and api["class"] == "unclassified" and api["outcome"] == "ok"
