"""The chat HTTP surface through the real app (TestClient, no listener): authentication like the rest of velaris.api,
structured errors, the event stream, files, the assistant, admin routes."""
import json
import secrets

import pytest

from velaris.tests.chat_support import ORG, api_client, chat_trace, send, signed, trace_text
from velaris.intel.llm import FakeLLM

BOT = "assistant:velaris"


@pytest.fixture
def api():
    return api_client()


def ok(r, status=200):
    assert r.status_code == status, r.text
    return r.json()


def err(r, status, code):
    assert r.status_code == status, r.text
    body = r.json()
    assert set(body) == {"error"} and body["error"]["code"] == code and set(body["error"]) == {"code", "message"}
    return body["error"]["message"]


def mk(api, sub, kind="public", name="general", members=()):
    return ok(send(api, "POST", "/chat/channels", {"kind": kind, "name": name, "members": list(members)}, sub=sub), 201)


def test_health_needs_no_signature_and_everything_else_does(api):
    assert api.get("/chat/health").json() == {"status": "ok"}
    for method, path in (("GET", "/chat/channels"), ("POST", "/chat/register"), ("GET", "/chat/search?q=x"),
                         ("GET", "/chat/files/" + "a" * 64), ("GET", "/chat/admin/settings")):
        err(api.request(method, path), 401, "unsigned")
    err(api.get("/chat/channels", headers={"X-Caller-Id": "admin", "X-Caller-Org": ORG}), 401, "unsigned")
    err(send(api, "GET", "/chat/channels", sub=""), 401, "bad_identity")
    h = signed("GET", "/chat/channels")
    assert api.get("/chat/channels", headers=h).status_code == 200
    err(api.get("/chat/channels", headers=h), 401, "replay")
    nonce = secrets.token_urlsafe(16)
    h = signed("POST", "/chat/register", b"", nonce=nonce)
    err(api.post("/chat/register", content=b'{"x":1}', headers=h), 401, "bad_signature")       # body altered after signing
    h = signed("GET", "/chat/search?q=a")
    err(api.get("/chat/search?q=b", headers=h), 401, "bad_signature")                           # query altered after signing


def test_another_organisation_and_forged_assistant_identities_are_refused(api):
    err(send(api, "GET", "/chat/channels", org="evil"), 403, "wrong_organisation")
    err(send(api, "POST", "/chat/register", sub=BOT), 403, "bad_identity")
    err(send(api, "POST", "/chat/channels", {"kind": "public", "name": "x"}, sub=BOT), 403, "bad_identity")


def test_the_whole_conversation_over_http(api):
    ch = mk(api, "alice", members=["bob"])
    cid = ch["id"]
    assert ch["members"][0] == {"id": "alice", "role": "owner"}
    reg = ok(send(api, "POST", "/chat/register", sub="bob"))
    assert reg["last_event_id"] == -1 and reg["snapshot"]["channels"][0]["id"] == cid
    r = send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "hello @[bob]", "topic": "intro", "local_id": "c1"}, sub="alice")
    msg = ok(r, 201)["message"]
    assert msg["mentions"] == ["bob"] and msg["topic"] == "intro"
    again = ok(send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "hello @[bob]", "topic": "intro", "local_id": "c1"}, sub="alice"))
    assert again["duplicate"] and again["message"]["id"] == msg["id"]
    got = ok(send(api, "GET", f"/chat/events?queue_id={reg['queue_id']}&last_event_id=-1&timeout=0", sub="bob"))
    assert [e["type"] for e in got["events"]] == ["message"] and got["events"][0]["id"] == 0
    assert ok(send(api, "GET", f"/chat/channels/{cid}/messages?topic=intro", sub="bob"))["messages"][0]["id"] == msg["id"]
    assert ok(send(api, "GET", "/chat/channels", sub="bob"))["channels"][0]["unread"] == 1
    ok(send(api, "POST", f"/chat/channels/{cid}/read", {}, sub="bob"))
    assert ok(send(api, "GET", "/chat/channels", sub="bob"))["channels"][0]["unread"] == 0
    ok(send(api, "PUT", f"/chat/messages/{msg['id']}/reactions/thumbsup", sub="bob"))
    edited = ok(send(api, "PATCH", f"/chat/messages/{msg['id']}", {"body": "hello again"}, sub="alice"))["message"]
    assert edited["body"] == "hello again" and edited["reactions"] == {"thumbsup": ["bob"]}
    assert [v["body"] for v in ok(send(api, "GET", f"/chat/messages/{msg['id']}/history", sub="bob"))["versions"]] == ["hello @[bob]", "hello again"]
    assert [m["id"] for m in ok(send(api, "GET", "/chat/search?q=hello&limit=5", sub="bob"))["messages"]] == [msg["id"]]
    assert ok(send(api, "GET", "/chat/search?q=hello", sub="cara"))["messages"] == []
    assert ok(send(api, "GET", f"/chat/channels/{cid}/topics", sub="bob"))["topics"][0]["topic"] == "intro"
    ok(send(api, "PUT", f"/chat/messages/{msg['id']}/pin", sub="alice"))
    assert ok(send(api, "GET", f"/chat/channels/{cid}/pins", sub="bob"))["messages"][0]["id"] == msg["id"]
    err(send(api, "PUT", f"/chat/messages/{msg['id']}/pin", sub="bob"), 403, "forbidden")
    ok(send(api, "PUT", f"/chat/channels/{cid}/draft", {"body": "wip", "topic": "intro"}, sub="bob"))
    assert ok(send(api, "GET", "/chat/drafts", sub="bob"))["drafts"][0]["body"] == "wip"
    ok(send(api, "DELETE", f"/chat/messages/{msg['id']}", sub="alice"))
    assert ok(send(api, "GET", f"/chat/channels/{cid}/messages", sub="bob"))["messages"][0]["deleted"] is True
    assert ok(send(api, "GET", "/chat/channels/public", sub="cara"))["channels"][0]["name"] == "general"
    assert ok(send(api, "POST", f"/chat/channels/{cid}/join", sub="cara"))["id"] == cid
    ok(send(api, "POST", f"/chat/channels/{cid}/members", {"user_id": "dan"}, sub="cara"))
    ok(send(api, "PUT", f"/chat/channels/{cid}/members/dan/role", {"role": "admin"}, sub="alice"))
    ok(send(api, "DELETE", f"/chat/channels/{cid}/members/dan", sub="alice"))
    ok(send(api, "POST", f"/chat/channels/{cid}/leave", sub="cara"))
    ok(send(api, "PATCH", f"/chat/channels/{cid}", {"retention_days": 30}, sub="alice"))
    assert ok(send(api, "DELETE", f"/chat/queues/{reg['queue_id']}", sub="bob")) == {"deleted": True}


def test_errors_are_structured_and_say_nothing_about_internals(api):
    cid = mk(api, "alice")["id"]
    err(send(api, "GET", "/chat/channels/999", sub="alice"), 404, "no_such_channel")
    err(send(api, "GET", "/chat/channels/abc", sub="alice"), 400, "invalid_request")
    err(send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "x", "evil": 1}, sub="alice"), 400, "bad_request")
    err(send(api, "POST", f"/chat/channels/{cid}/messages", {}, sub="alice"), 400, "bad_request")
    err(send(api, "POST", f"/chat/channels/{cid}/messages", raw=b"{nope", sub="alice"), 400, "invalid_json")
    err(send(api, "POST", f"/chat/channels/{cid}/messages", raw=b"[1]", sub="alice"), 400, "bad_request")
    err(send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "x" * 10_001}, sub="alice"), 413, "body_too_long")
    err(send(api, "POST", f"/chat/channels/{cid}/messages", raw=b"{" + b" " * (65 * 1024) + b"}", sub="alice"), 413, "too_large")
    err(send(api, "GET", f"/chat/channels/{cid}/messages?limit=abc", sub="alice"), 400, "bad_request")
    err(send(api, "GET", f"/chat/channels/{cid}/messages?limit=1000", sub="alice"), 400, "bad_request")
    err(send(api, "GET", "/chat/events?queue_id=nope", sub="alice"), 410, "bad_queue")
    err(send(api, "GET", "/chat/nothing-here", sub="alice"), 404, "not_found")
    msg = err(send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "x"}, sub="mallory"), 403, "forbidden")
    assert "mallory" not in msg
    err(send(api, "GET", f"/chat/channels/{cid}/messages", sub="mallory"), 403, "forbidden")           # public: visible, not readable
    private = mk(api, "alice", kind="private", name="secret")["id"]
    err(send(api, "GET", f"/chat/channels/{private}/messages", sub="mallory"), 404, "no_such_channel")


def test_long_poll_times_out_with_an_empty_list(api):
    mk(api, "alice", members=["bob"])
    q = ok(send(api, "POST", "/chat/register", sub="bob"))["queue_id"]
    assert ok(send(api, "GET", f"/chat/events?queue_id={q}&last_event_id=-1&timeout=0.2", sub="bob")) == {"events": []}
    err(send(api, "GET", f"/chat/events?queue_id={q}&last_event_id=-1&timeout=abc", sub="bob"), 400, "bad_request")
    err(send(api, "GET", f"/chat/events?queue_id={q}&last_event_id=-1", sub="alice"), 410, "bad_queue")   # someone else's queue


def stream(api, path, sub, headers=None):
    h = signed("GET", path, sub=sub)
    h.update(headers or {})
    with api.stream("GET", path, headers=h) as r:
        return r.status_code, r.headers.get("content-type", ""), r.read().decode()


def test_server_sent_events_stream(api):
    cid = mk(api, "alice", members=["bob"])["id"]
    q = ok(send(api, "POST", "/chat/register", sub="bob"))["queue_id"]
    send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "first"}, sub="alice")
    send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "second\nwith a newline"}, sub="alice")
    status, ctype, text = stream(api, f"/chat/events/stream?queue_id={q}&last_event_id=-1&duration=0.3", "bob")
    assert status == 200 and ctype.startswith("text/event-stream")
    frames = [f for f in text.split("\n\n") if f.startswith("id:")]
    assert [f.split("\n")[0] for f in frames] == ["id: 0", "id: 1"] and frames[0].split("\n")[1] == "event: message"
    assert json.loads(frames[1].split("data: ", 1)[1])["message"]["body"] == "second\nwith a newline" and ": keepalive" in text
    # nothing was acknowledged by the stream itself; a reconnect says what it has with Last-Event-ID
    _, _, again = stream(api, f"/chat/events/stream?queue_id={q}&duration=0.2", "bob", {"Last-Event-ID": "0"})
    assert [f.split("\n")[0] for f in again.split("\n\n") if f.startswith("id:")] == ["id: 1"]
    _, _, none = stream(api, f"/chat/events/stream?queue_id={q}&last_event_id=1&duration=0.2", "bob")
    assert "id:" not in none
    status, _, body = stream(api, "/chat/events/stream?queue_id=nope&duration=0.1", "bob")
    assert status == 410 and json.loads(body)["error"]["code"] == "bad_queue"


def test_removed_member_gets_nothing_over_the_wire(api):
    cid = mk(api, "alice", kind="private", name="p", members=["bob"])["id"]
    q = ok(send(api, "POST", "/chat/register", sub="bob"))["queue_id"]
    send(api, "DELETE", f"/chat/channels/{cid}/members/bob", sub="alice")
    send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "after removal"}, sub="alice")
    events = ok(send(api, "GET", f"/chat/events?queue_id={q}&last_event_id=-1", sub="bob"))["events"]
    assert [e["type"] for e in events] == ["member"] and "after removal" not in json.dumps(events)


PNG = b"\x89PNG\r\n\x1a\n" + b"1" * 64


def test_files_over_http(api):
    cid = mk(api, "alice", members=["bob"])["id"]
    up = ok(send(api, "POST", "/chat/files?name=logo.png&content_type=image/png", raw=PNG, sub="alice"), 201)
    assert up["content_type"] == "image/png"
    err(send(api, "GET", f"/chat/files/{up['hash']}", sub="bob"), 404, "no_such_file")
    ok(send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "logo", "attachments": [up["hash"]]}, sub="alice"), 201)
    r = send(api, "GET", f"/chat/files/{up['hash']}", sub="bob")
    assert r.status_code == 200 and r.content == PNG and r.headers["content-type"] == "image/png"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["content-disposition"].startswith("attachment;")
    assert "sandbox" in r.headers["content-security-policy"]
    err(send(api, "GET", f"/chat/files/{up['hash']}", sub="mallory"), 404, "no_such_file")
    err(send(api, "POST", "/chat/files?name=x.png&content_type=application/pdf", raw=PNG, sub="alice"), 415, "type_mismatch")
    err(send(api, "POST", "/chat/files?name=x", raw=b"\x00\x01\x02", sub="alice"), 415, "unsupported_type")
    err(send(api, "POST", "/chat/files?name=x", raw=b"", sub="alice"), 400, "empty_file")
    big = b"%PDF-" + b"0" * (10 * 1024 * 1024)
    err(send(api, "POST", "/chat/files?name=big.pdf", raw=big, sub="alice"), 413, "too_large")


def test_rate_limit_is_a_429(api):
    cid = mk(api, "alice")["id"]
    codes = [send(api, "POST", f"/chat/channels/{cid}/messages", {"body": f"m{i}"}, sub="alice").status_code for i in range(14)]
    assert codes[:3] == [201, 201, 201] and 429 in codes
    r = send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "again"}, sub="alice")
    assert r.status_code == 429 and r.json()["error"]["code"] == "rate_limited"


def test_admin_routes_need_the_chat_admin_role(api):
    cid = mk(api, "alice")["id"]
    send(api, "POST", f"/chat/channels/{cid}/messages", {"body": "export me"}, sub="alice")
    for method, path, body in (("GET", "/chat/admin/settings", None), ("PUT", "/chat/admin/settings", {"ai_enabled": False}),
                               ("GET", f"/chat/admin/channels/{cid}/export", None), ("PUT", f"/chat/admin/channels/{cid}/hold", {"hold": True}),
                               ("POST", "/chat/admin/sweep", None), ("POST", "/chat/admin/messages/1/erase", None),
                               ("POST", "/chat/admin/users/alice/erase", None), ("GET", "/chat/admin/users/bob/export", None)):
        err(send(api, method, path, body, sub="alice"), 403, "forbidden")
    adm = dict(sub="root", roles=["chat_admin"])
    assert ok(send(api, "GET", f"/chat/admin/channels/{cid}/export", **adm))["messages"][0]["body"] == "export me"
    assert ok(send(api, "PUT", f"/chat/admin/channels/{cid}/hold", {"hold": True}, **adm))["legal_hold"] is True
    err(send(api, "DELETE", "/chat/messages/1", sub="alice"), 403, "forbidden")                           # legal hold
    assert ok(send(api, "PUT", "/chat/admin/settings", {"retention_days": 90}, **adm))["retention_days"] == 90
    assert ok(send(api, "POST", "/chat/admin/sweep", **adm)) == {"expired": 0, "purged": 0}
    assert ok(send(api, "GET", "/chat/me/export", sub="alice"))["messages"][0]["body"] == "export me"
    assert ok(send(api, "GET", "/chat/admin/users/alice/export", **adm))["user"] == "alice"
    err(send(api, "POST", "/chat/admin/messages/1/erase", **adm), 403, "forbidden")                       # legal hold again
    assert ok(send(api, "POST", "/chat/admin/users/alice/erase", **adm))["messages_held_by_legal_hold"] == 1
    assert chat_trace("channel.export")[-1]["caller"] == "root"
    assert "export me" not in trace_text()


def test_assistant_over_http_draft_confirm_and_approval():
    llm = FakeLLM(lambda p, m: json.dumps({"text": "Drafted reply.", "propose": {"tool": "post_message", "args": {"channel_id": 2, "body": "via approval"}}})
                  if "ops please" in p else json.dumps({"text": "Short answer.", "propose": None}))
    api = api_client(llm=llm)
    gen = mk(api, "alice", members=["bob"])["id"]
    ops = mk(api, "alice", name="ops", members=["bob"])["id"]
    ok(send(api, "POST", f"/chat/channels/{gen}/members", {"user_id": BOT}, sub="alice"))
    err(send(api, "POST", f"/chat/channels/{gen}/members", {"user_id": BOT}, sub="bob"), 403, "forbidden")
    ok(send(api, "POST", f"/chat/channels/{gen}/messages", {"body": f"@[{BOT}] what is up?"}, sub="bob"), 201)
    msgs = ok(send(api, "GET", f"/chat/channels/{gen}/messages", sub="alice"))["messages"]
    assert msgs[-1]["sender"] == BOT and msgs[-1]["body"] == "Short answer."                      # the background run finished
    ok(send(api, "POST", f"/chat/channels/{gen}/messages", {"body": f"@[{BOT}] draft something"}, sub="bob"), 201)
    drafts = ok(send(api, "GET", "/chat/assistant/drafts", sub="bob"))["drafts"]
    assert len(drafts) == 1 and ok(send(api, "GET", "/chat/assistant/drafts", sub="alice"))["drafts"] == []
    err(send(api, "POST", f"/chat/assistant/drafts/{drafts[0]['draft_id']}/confirm", {}, sub="alice"), 404, "no_such_draft")
    posted = ok(send(api, "POST", f"/chat/assistant/drafts/{drafts[0]['draft_id']}/confirm", {}, sub="bob"))["message"]
    assert posted["sender"] == "bob" and posted["ai_assisted"]
    ok(send(api, "POST", f"/chat/channels/{gen}/messages", {"body": f"@[{BOT}] ops please"}, sub="bob"), 201)
    assert ok(send(api, "GET", "/chat/assistant/proposals", sub="alice"))["proposals"] == []          # not until bob confirms
    prop = ok(send(api, "GET", "/chat/assistant/proposals", sub="bob"))["proposals"]
    assert len(prop) == 1 and prop[0]["requester"] == "bob" and prop[0]["args"]["channel_id"] == ops
    path = f"/chat/assistant/proposals/{prop[0]['run_id']}/decide"
    err(send(api, "POST", path, {"call_hash": prop[0]["call_hash"], "approve": True}, sub="alice"), 409, "requester_not_confirmed")
    cpath = f"/chat/assistant/proposals/{prop[0]['run_id']}/confirm"
    err(send(api, "POST", cpath, {"call_hash": prop[0]["call_hash"]}, sub="alice"), 404, "no_such_proposal")
    err(send(api, "POST", cpath, {"call_hash": "0" * 64}, sub="bob"), 409, "hash_mismatch")
    assert ok(send(api, "POST", cpath, {"call_hash": prop[0]["call_hash"]}, sub="bob"))["status"] == "confirmed"
    assert len(ok(send(api, "GET", "/chat/assistant/proposals", sub="alice"))["proposals"]) == 1
    assert ok(send(api, "GET", f"/chat/channels/{ops}/messages", sub="bob"))["messages"] == []
    path = f"/chat/assistant/proposals/{prop[0]['run_id']}/decide"
    err(send(api, "POST", path, {"call_hash": prop[0]["call_hash"], "approve": True}, sub="bob"), 403, "four_eyes")
    err(send(api, "POST", path, {"call_hash": prop[0]["call_hash"]}, sub="alice"), 400, "bad_request")
    assert ok(send(api, "POST", path, {"call_hash": prop[0]["call_hash"], "approve": True}, sub="alice"))["status"] == "approved"
    assert ok(send(api, "GET", f"/chat/channels/{ops}/messages", sub="bob"))["messages"][0]["body"] == "via approval"
    ok(send(api, "PATCH", f"/chat/channels/{gen}", {"ai_enabled": False}, sub="alice"))
    n = len(llm.calls)
    ok(send(api, "POST", f"/chat/channels/{gen}/messages", {"body": f"@[{BOT}] anyone?"}, sub="bob"), 201)
    assert len(llm.calls) == n


def test_assistant_without_a_model_is_quiet_over_http(monkeypatch):
    for k in ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "AWS_BEARER_TOKEN_BEDROCK", "OLLAMA_MODEL"):
        monkeypatch.delenv(k, raising=False)
    api = api_client(llm=None)
    gen = mk(api, "alice")["id"]
    ok(send(api, "POST", f"/chat/channels/{gen}/members", {"user_id": BOT}, sub="alice"))
    ok(send(api, "POST", f"/chat/channels/{gen}/messages", {"body": f"@[{BOT}] hello?"}, sub="alice"), 201)
    assert [m["sender"] for m in ok(send(api, "GET", f"/chat/channels/{gen}/messages", sub="alice"))["messages"]] == ["alice"]
    assert chat_trace("assistant.notice")[-1]["code"] == "not_configured"


def test_existing_api_is_unchanged(api):
    assert api.get("/health").json() == {"status": "ok"}
    assert api.get("/agents").json()["error"]["code"] == "unsigned"
    assert api.get("/nowhere").json()["error"]["code"] == "not_found"


def test_open_streams_do_not_each_hold_a_worker_thread(api):
    """KAN-136: the stream is an async generator; a sync one parked a thread per stream."""
    import inspect
    from velaris.chat import api as chat_api
    src = inspect.getsource(chat_api)
    assert "async def frames()" in src and "def frames() -> Iterator" not in src
