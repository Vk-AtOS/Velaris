"""The /mail HTTP API through the real app: signed requests, identity from the assertion only, structured errors, the whole flow."""
import base64
import json
import secrets

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from velaris.api.app import Settings, create_app
from velaris.api.auth import make_assertion, sign
from velaris.intel import trace
from velaris.intel.llm import FakeLLM
from velaris.mail import api as mail_api
from velaris.mail.api import MailDeps
from velaris.mail.inbound import InboundPipeline
from velaris.mail.outbound import Outbound
from velaris.mail.smtp import Envelope
from velaris.mail.store import MailStore
from velaris.tests.mail_helpers import Clock, FakeRelay, FakeResolver, raw_mail
from velaris.tests.test_mail_connector import FakeImap, PASSWORD

SECRET = b"m" * 32
KEY = Ed25519PrivateKey.generate()
ADMIN = dict(sub="admin", roles=["mail_admin"])
ALICE, BOB, CAROL = dict(sub="alice"), dict(sub="bob"), dict(sub="carol", roles=["mail_approver"])


class Env:
    pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    e = Env()
    e.clock, e.relay = Clock(), FakeRelay()
    e.store = MailStore(clock=e.clock)
    e.out = Outbound(e.store, relay=e.relay, clock=e.clock, flow_path=str(tmp_path / "mailflow.db"))
    e.inb = InboundPipeline(e.store, FakeResolver(), outbound=e.out)
    e.out.local_delivery = e.inb.deliver_local
    e.llm = FakeLLM(lambda p, m: "A short summary.")
    e.imap = FakeImap({"INBOX": {"validity": 1, "msgs": {1: (raw_mail(mid="remote1@x", subject="from the server"), False)}}})
    mail_api.configure(MailDeps(e.store, e.out, e.inb, lambda cfg: e.imap, lambda n: PASSWORD if n == "mail.alice" else None, e.llm))
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), flow_db=str(tmp_path / "flow.db"), org="acme", llm=e.llm)
    e.client = TestClient(create_app(settings, engine=object()))
    yield e
    mail_api.configure(None)


def call(env, method, path, body=None, *, who=ALICE, org="acme", raw=None, key=KEY):
    content = raw if raw is not None else (b"" if body is None else json.dumps(body).encode())
    nonce = secrets.token_urlsafe(16)
    identity = make_assertion(key, sub=who["sub"], org=org, roles=who.get("roles", ()), nonce=nonce)
    return env.client.request(method, path, content=content, headers=sign(SECRET, method, path, content, identity, nonce=nonce))


def setup_world(env):
    assert call(env, "PUT", "/mail/settings", {"local_domains": ["acme.com"]}, who=ADMIN).json()["error"]["code"] == "domain_unverified"
    claim = call(env, "POST", "/mail/domains", {"domain": "acme.com"}, who=ADMIN)
    assert claim.status_code == 201 and claim.json()["status"] == "pending"
    assert call(env, "POST", "/mail/domains/verify", {"domain": "acme.com"}, who=ADMIN).json()["status"] == "pending"
    env.inb.resolver.z["txt"]["_velaris.acme.com"] = [claim.json()["record"]["value"]]
    assert call(env, "POST", "/mail/domains/verify", {"domain": "acme.com"}, who=ADMIN).json()["status"] == "verified"
    assert call(env, "PUT", "/mail/settings", {"local_domains": ["acme.com"]}, who=ADMIN).status_code == 200
    ids = {}
    for n in ("alice", "bob"):
        r = call(env, "POST", "/mail/mailboxes", {"address": f"{n}@acme.com", "owner_id": n}, who=ADMIN)
        assert r.status_code == 201
        ids[n] = r.json()["id"]
    return ids


def receive(env, rcpt="alice@acme.com", **kw):
    kw.setdefault("to", rcpt)
    assert env.inb.deliver(Envelope("h.org", "192.0.2.1", kw.get("frm", "x@ext.org"), [rcpt], raw_mail(**kw)))[0] == 250


def test_authentication_is_the_apps_and_identity_comes_only_from_the_assertion(env):
    c = env.client
    assert c.get("/mail/mailboxes").json()["error"]["code"] == "unsigned"
    assert c.get("/mail/mailboxes", headers={"X-Caller-Id": "admin", "X-Caller-Org": "acme"}).status_code == 401
    r = call(env, "GET", "/mail/mailboxes", org="evilcorp")
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_organisation"
    assert call(env, "GET", "/mail/mailboxes", key=Ed25519PrivateKey.generate()).json()["error"]["code"] == "bad_identity"
    ids = setup_world(env)
    assert [m["address"] for m in call(env, "GET", "/mail/mailboxes").json()["mailboxes"]] == ["alice@acme.com"]
    assert call(env, "GET", f"/mail/mailboxes/{ids['alice']}/folders", who=BOB).status_code == 404         # alice's mailbox does not exist for bob
    forged = call(env, "POST", f"/mail/mailboxes/{ids['alice']}/drafts", {"to": ["bob@acme.com"], "sub": "alice", "owner_id": "alice"}, who=BOB)
    assert forged.status_code == 404                                                                         # a body can never name who is acting
    assert call(env, "POST", "/mail/mailboxes", {"address": "x@acme.com"}, who=ALICE).status_code == 403


def test_errors_are_structured_and_never_carry_exception_text_or_input(env):
    ids = setup_world(env)
    mb = ids["alice"]
    for method, path, body, status, code in [
        ("POST", f"/mail/mailboxes/{mb}/folders", {"name": "bad/name"}, 400, "bad_request"),
        ("PATCH", f"/mail/mailboxes/{mb}/messages/nope", {"seen": True}, 404, "not_found"),
        ("PATCH", f"/mail/mailboxes/{mb}/messages/x", {"hack": 1}, 400, "bad_request"),
        ("GET", f"/mail/mailboxes/{mb}/messages?limit=abc", None, 400, "bad_request"),
        ("GET", f"/mail/mailboxes/{mb}/messages?q=%21%21", None, 400, "bad_request"),
        ("DELETE", f"/mail/mailboxes/{mb}", None, 400, "confirm_required"),
        ("POST", "/mail/submissions/nope/cancel", None, 404, "not_found"),
        ("GET", "/mail/mailboxes/..%2F..%2Fetc/folders", None, 404, "not_found"),
    ]:
        r = call(env, method, path, body)
        assert (r.status_code, r.json()["error"]["code"]) == (status, code), (path, r.text)
        assert set(r.json()["error"]) == {"code", "message"} and "Traceback" not in r.text and "sqlite" not in r.text.lower()
    assert call(env, "POST", f"/mail/mailboxes/{mb}/drafts", raw=b"not json").json()["error"]["code"] == "invalid_json"
    assert call(env, "POST", f"/mail/mailboxes/{mb}/drafts", raw=b"[1,2]").json()["error"]["code"] == "bad_request"
    big = call(env, "POST", f"/mail/mailboxes/{mb}/folders", raw=b'{"name":"' + b"x" * 70_000 + b'"}')
    assert big.status_code == 413 and big.json()["error"]["code"] == "too_large"


def test_reading_flow_list_get_sanitised_html_flags_search_attachments_delete_restore(env):
    ids = setup_world(env)
    mb = ids["alice"]
    html = (b"From: x@ext.org\r\nTo: alice@acme.com\r\nSubject: Offer\r\nMessage-ID: <h1@x>\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=B\r\n\r\n"
            b"--B\r\nContent-Type: text/html\r\n\r\n<p onclick=x()>Hello <script>steal()</script><img src=http://t.example/p.gif><a href=https://evil.test/x>link</a></p>\r\n"
            b'--B\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename="../a b.pdf"\r\nContent-Transfer-Encoding: base64\r\n\r\nSGVsbG8=\r\n--B--\r\n')
    assert env.inb.deliver(Envelope("h.org", "192.0.2.1", "x@ext.org", ["alice@acme.com"], html))[0] == 250
    lst = call(env, "GET", f"/mail/mailboxes/{mb}/messages").json()
    assert lst["total"] == 1 and lst["messages"][0]["attachments"] == 1 and lst["messages"][0]["subject"] == "Offer"
    m = lst["messages"][0]["id"]
    full = call(env, "GET", f"/mail/mailboxes/{mb}/messages/{m}").json()
    assert "script" not in full["body_html"] and "onclick" not in full["body_html"] and "t.example" not in full["body_html"] and "(evil.test)" in full["body_html"]
    assert full["blocked_images"] == 1 and "spf=" in full["auth_results"]
    sha = full["attachment_list"][0]["sha256"]
    dl = call(env, "GET", f"/mail/mailboxes/{mb}/messages/{m}/attachments/{sha}")
    assert dl.content == b"Hello" and dl.headers["content-type"] == "application/octet-stream" and dl.headers["x-content-type-options"] == "nosniff"
    assert "attachment;" in dl.headers["content-disposition"] and "/" not in dl.headers["content-disposition"].split("filename=")[1]
    assert call(env, "GET", f"/mail/mailboxes/{mb}/messages/{m}/attachments/{'0' * 64}").status_code == 404
    p = call(env, "PATCH", f"/mail/mailboxes/{mb}/messages/{m}", {"seen": True, "flagged": True, "add_labels": ["work"]}).json()
    assert p["seen"] and p["flagged"] and p["labels"] == ["work"]
    assert call(env, "GET", f"/mail/mailboxes/{mb}/messages?q=offer").json()["total"] == 1
    assert call(env, "GET", f"/mail/mailboxes/{mb}/messages?unread=1").json()["total"] == 0
    assert call(env, "GET", f"/mail/mailboxes/{mb}/messages?label=work&flagged=1").json()["total"] == 1
    assert call(env, "GET", f"/mail/mailboxes/{mb}/threads/{full['thread_id']}").json()["messages"][0]["id"] == m
    assert call(env, "DELETE", f"/mail/mailboxes/{mb}/messages/{m}").json() == {"deleted": "soft"}
    assert call(env, "GET", f"/mail/mailboxes/{mb}/messages").json()["total"] == 0
    assert call(env, "POST", f"/mail/mailboxes/{mb}/messages/{m}/restore").json()["folder_role"] == "inbox"
    assert [f["role"] for f in call(env, "GET", f"/mail/mailboxes/{mb}/folders").json()["folders"]][:3] == ["inbox", "drafts", "sent"]
    assert call(env, "DELETE", f"/mail/mailboxes/{mb}/messages/{m}?permanent=1").status_code == 409


def test_compose_submit_undo_and_send_timeline_over_http(env):
    ids = setup_world(env)
    mb = ids["alice"]
    d = call(env, "POST", f"/mail/mailboxes/{mb}/drafts", {"to": ["bob@acme.com"], "subject": "Lunch", "text": "noon?"})
    assert d.status_code == 201
    did = d.json()["id"]
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/drafts/{did}", {"text": "12:30?"}).json()["body_text"] == "12:30?"
    sub = call(env, "POST", f"/mail/mailboxes/{mb}/drafts/{did}/submit")
    assert sub.status_code == 202
    s = sub.json()
    assert (s["state"], s["undoStatus"], s["canCancel"]) == ("approved", "pending", True) and s["sendAt"] == env.clock() + 30
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/drafts/{did}", {"text": "x"}).json()["error"]["code"] == "locked"
    env.clock.advance(5)
    canc = call(env, "POST", f"/mail/submissions/{s['id']}/cancel").json()
    assert (canc["state"], canc["undoStatus"]) == ("canceled", "canceled")
    s2 = call(env, "POST", f"/mail/mailboxes/{mb}/drafts/{did}/submit").json()
    env.clock.advance(31)
    listing = call(env, "GET", f"/mail/mailboxes/{mb}/submissions").json()["submissions"]
    assert listing[0]["state"] == "sent" and listing[0]["id"] == s2["id"]                    # due sends go out when the mailbox is looked at
    r = call(env, "POST", f"/mail/submissions/{s2['id']}/cancel")
    assert r.status_code == 409 and r.json()["error"]["code"] == "cannot_unsend"
    assert call(env, "GET", f"/mail/mailboxes/{ids['bob']}/messages", who=BOB).json()["messages"][0]["subject"] == "Lunch"
    assert call(env, "GET", f"/mail/submissions/{s2['id']}", who=BOB).status_code == 404       # bob did not send it


def test_external_send_approval_over_http_four_eyes_and_hash_binding(env):
    ids = setup_world(env)
    mb = ids["alice"]
    did = call(env, "POST", f"/mail/mailboxes/{mb}/drafts", {"to": ["client@ext.org"], "subject": "Quote", "text": "see attached terms"}).json()["id"]
    s = call(env, "POST", f"/mail/mailboxes/{mb}/drafts/{did}/submit").json()
    assert s["state"] == "awaiting_approval" and s["reasons"][0]["code"] == "external_recipient"
    assert call(env, "GET", "/mail/approvals", who=ALICE).json()["approvals"] == []
    appr = call(env, "GET", "/mail/approvals", who=CAROL).json()["approvals"]
    assert appr[0]["preview"]["to"] == ["client@ext.org"] and appr[0]["payload_hash"] == s["payload_hash"]
    body = {"approve": True, "payload_hash": s["payload_hash"]}
    own = call(env, "POST", f"/mail/submissions/{s['id']}/decide", body, who=dict(sub="alice", roles=["mail_approver"]))
    assert own.status_code == 403 and own.json()["error"]["code"] == "four_eyes"
    assert call(env, "POST", f"/mail/submissions/{s['id']}/decide", body, who=BOB).json()["error"]["code"] == "forbidden"
    assert call(env, "POST", f"/mail/submissions/{s['id']}/decide", {**body, "payload_hash": "f" * 64}, who=CAROL).json()["error"]["code"] == "hash_mismatch"
    assert call(env, "POST", f"/mail/submissions/{s['id']}/decide", {"approve": "yes"}, who=CAROL).json()["error"]["code"] == "bad_request"
    ok = call(env, "POST", f"/mail/submissions/{s['id']}/decide", body, who=CAROL).json()
    assert ok["state"] == "approved" and ok["approved_by"] == "carol"
    env.clock.advance(31)
    assert call(env, "POST", "/mail/outbox/process", who=ALICE).status_code == 403
    assert len(call(env, "POST", "/mail/outbox/process", who=ADMIN).json()["processed"]) == 1 and env.relay.sent[0]["rcpts"] == ["client@ext.org"]


def test_rules_settings_aliases_delegates_quota_hold_over_http(env):
    ids = setup_world(env)
    mb = ids["alice"]
    rule = {"name": "news", "conditions": [{"field": "subject", "op": "contains", "value": "news"}], "actions": [{"type": "label", "label": "news"}]}
    r = call(env, "POST", f"/mail/mailboxes/{mb}/rules", rule)
    assert r.status_code == 201
    rid = r.json()["id"]
    assert call(env, "POST", f"/mail/mailboxes/{mb}/rules", {**rule, "actions": [{"type": "delete"}]}).json()["error"]["code"] == "bad_rule"
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/rules/{rid}", {**rule, "enabled": False}).json()["enabled"] is False
    receive(env, subject="weekly news")
    assert call(env, "POST", f"/mail/mailboxes/{mb}/rules/dry-run", rule).json()["would_match"]
    assert call(env, "GET", f"/mail/mailboxes/{mb}/rules", who=BOB).status_code == 404
    assert call(env, "DELETE", f"/mail/mailboxes/{mb}/rules/{rid}").json() == {"deleted": True}
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/settings", {"signature": "Alice", "vacation": {"enabled": True, "body": "away"}}).json()["signature"] == "Alice"
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/aliases", {"address": "ops@acme.com"}, who=ALICE).status_code == 403
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/aliases", {"address": "ops@acme.com"}, who=ADMIN).json()["aliases"] == ["ops@acme.com"]
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/delegates", {"user_id": "bob", "rights": ["read"]}).json()["rights"] == ["read"]
    assert call(env, "GET", f"/mail/mailboxes/{mb}/messages", who=BOB).status_code == 200
    assert call(env, "PATCH", f"/mail/mailboxes/{mb}/messages/{call(env, 'GET', f'/mail/mailboxes/{mb}/messages', who=BOB).json()['messages'][0]['id']}", {"seen": True}, who=BOB).status_code == 403
    assert call(env, "DELETE", f"/mail/mailboxes/{mb}/delegates?user_id=bob").json() == {"removed": True}
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/quota", {"quota_bytes": 5_000_000}, who=ADMIN).json() == {"quota_bytes": 5_000_000}
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/quota", {"quota_bytes": 5_000_000}, who=ALICE).status_code == 403
    assert call(env, "PUT", f"/mail/mailboxes/{mb}/legal-hold", {"on": True}, who=ADMIN).json()["legal_hold"] is True
    assert call(env, "GET", "/mail/settings").json()["local_domains"] == ["acme.com"]
    assert call(env, "PUT", "/mail/settings", {"undo_window_s": 0}, who=ALICE).status_code == 403
    assert call(env, "PUT", "/mail/settings", {"undo_window_s": 0}, who=ADMIN).json()["undo_window_s"] == 0
    assert call(env, "GET", "/mail/settings/dkim", who=ADMIN).json()["status"] == "not_configured"
    call(env, "PUT", "/mail/settings", {"dkim_domains": ["acme.com"]}, who=ADMIN)
    rec = call(env, "GET", "/mail/settings/dkim", who=ADMIN).json()["records"][0]
    assert rec["name"] == "velaris._domainkey.acme.com" and rec["value"].startswith("v=DKIM1; k=rsa; p=")
    assert call(env, "POST", "/mail/retention/run", who=ADMIN).json().keys() >= {"trash", "spam"}


def test_connector_endpoints_and_sync(env):
    ids = setup_world(env)
    mb = ids["alice"]
    cfg = {"imap_host": "imap.example.com", "username": "alice@example.com", "secret_name": "mail.alice"}
    assert call(env, "POST", f"/mail/mailboxes/{mb}/sync").json()["error"]["code"] == "no_account"
    assert call(env, "POST", f"/mail/mailboxes/{mb}/accounts", cfg, who=ALICE).status_code == 403
    assert call(env, "POST", f"/mail/mailboxes/{mb}/accounts", {**cfg, "imap_host": "127.0.0.1"}, who=ADMIN).json()["error"]["code"] == "bad_host"
    acc = call(env, "POST", f"/mail/mailboxes/{mb}/accounts", cfg, who=ADMIN)
    assert acc.status_code == 201 and "password" not in acc.text
    out = call(env, "POST", f"/mail/mailboxes/{mb}/sync").json()
    assert out["synced"]["stored"] == 1 and out["errors"] == []
    assert call(env, "GET", f"/mail/mailboxes/{mb}/messages").json()["messages"][0]["subject"] == "from the server"
    assert call(env, "GET", f"/mail/mailboxes/{mb}/accounts").json()["accounts"][0]["folders"] == 1


def test_assistant_endpoints_and_not_configured(env):
    ids = setup_world(env)
    mb = ids["alice"]
    receive(env, subject="Question", frm="boss@ext.org", body="Can you confirm by 2026-12-01?")
    m = call(env, "GET", f"/mail/mailboxes/{mb}/messages").json()["messages"][0]
    s = call(env, "POST", f"/mail/mailboxes/{mb}/assistant/summarise", {"thread_id": m["thread_id"]}).json()
    assert s["status"] == "ok" and s["summary"] == "A short summary."
    d = call(env, "POST", f"/mail/mailboxes/{mb}/assistant/draft-reply", {"message_id": m["id"], "instruction": "confirm"})
    assert d.status_code == 201 and d.json()["needs_second_approver"] and d.json()["draft"]["to"] == ["boss@ext.org"]
    sub = call(env, "POST", f"/mail/mailboxes/{mb}/drafts/{d.json()['draft']['id']}/submit").json()
    assert sub["state"] == "awaiting_approval" and sub["origin"] == "assistant"
    assert call(env, "POST", f"/mail/mailboxes/{mb}/assistant/triage", {"message_id": m["id"]}, who=BOB).status_code == 404
    env.llm.script = lambda p, mo: (_ for _ in ()).throw(__import__("velaris.intel.llm", fromlist=["x"]).LLMError("down"))
    assert call(env, "POST", f"/mail/mailboxes/{mb}/assistant/summarise", {"thread_id": m["thread_id"]}).json()["status"] == "not_configured"


def test_export_and_erase_over_http_and_every_call_is_traced_without_content(env):
    ids = setup_world(env)
    mb = ids["alice"]
    receive(env, subject="Highly private subject", frm="friend@ext.org")
    exp = call(env, "GET", f"/mail/mailboxes/{mb}/export").json()
    assert exp["messages"][0]["subject"] == "Highly private subject"
    assert call(env, "GET", f"/mail/mailboxes/{mb}/export", who=BOB).status_code == 404
    assert call(env, "DELETE", f"/mail/mailboxes/{mb}?confirm=erase", who=BOB).status_code == 404
    assert call(env, "DELETE", f"/mail/mailboxes/{mb}?confirm=erase").json() == {"erased": True, "messages": 1}
    assert call(env, "GET", f"/mail/mailboxes/{mb}/folders").status_code == 404
    entries = list(trace.entries())
    blob = json.dumps(entries)
    assert "Highly private subject" not in blob and "friend@ext.org" not in blob and "alice@acme.com" not in blob
    api = [e["payload"] for e in entries if e["actor"] == "api" and e["action"].startswith("mail.")]
    assert api and all(p["caller"] and p["org"] == "acme" for p in api) and {"mail.export", "mail.erase"} <= {e["action"] for e in entries if e["actor"] == "api"}
    assert trace.verify()["ok"]


def test_a_draft_may_carry_attachments_beyond_64_kib_but_other_bodies_stay_small(env):
    """KAN-108: the app-wide 64 KiB body cap limited attachments to about 45 KB."""
    ids = setup_world(env)
    mb = ids["alice"]
    data = base64.b64encode(b"x" * 300_000).decode()
    r = call(env, "POST", f"/mail/mailboxes/{mb}/drafts", {"to": ["bob@acme.com"], "subject": "big", "text": "see attached",
                                                          "attachments": [{"name": "a.bin", "data_b64": data}]})
    assert r.status_code == 201, r.text
    over = call(env, "POST", f"/mail/mailboxes/{mb}/folders", {"name": "x" * 70_000})
    assert over.status_code == 413 and over.json()["error"]["code"] == "too_large"
    huge = call(env, "POST", f"/mail/mailboxes/{mb}/drafts", raw=b'{"text": "' + b"x" * (17 * 1024 * 1024) + b'"}')
    assert huge.status_code == 413
