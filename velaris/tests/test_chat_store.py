"""The chat service on its store: channels, messages, search scope, retention, erasure, files, organisations."""
import io
import os
import stat
import zipfile

import pytest

from velaris.tests.chat_support import ADMIN, ALICE, BOB, CARA, DAN, ORG, chat_trace, service, trace_text, who
from velaris.chat import files as chat_files
from velaris.chat.errors import ChatError
from velaris.chat.policy import Limits, TokenBucket
from velaris.chat.store import Store
from velaris.intel import trace

DAY = 86400.0


def code(fn, *a, **k):
    with pytest.raises(ChatError) as e:
        fn(*a, **k)
    return e.value.code


@pytest.fixture
def s():
    return service()


@pytest.fixture
def room(s):
    ch = s.create_channel(ALICE, "public", "general", ["bob"])
    return s, ch["id"]


def test_store_file_is_owner_only_and_wal(s):
    mode = stat.S_IMODE(os.stat(s.store.path).st_mode)
    assert mode == 0o600
    assert s.store.db.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    s.post(ALICE, s.create_channel(ALICE, "private", "p")["id"], "x")
    for side in ("-wal", "-shm"):
        p = str(s.store.path) + side
        if os.path.exists(p):
            assert stat.S_IMODE(os.stat(p).st_mode) & 0o077 == 0


def test_channels_and_membership(s):
    pub = s.create_channel(ALICE, "public", "general", ["bob"])
    assert pub["created"] and {m["id"]: m["role"] for m in pub["members"]} == {"alice": "owner", "bob": "member"}
    assert code(s.create_channel, BOB, "public", "general") == "name_taken"
    assert code(s.create_channel, BOB, "wiki", "x") == "bad_kind"
    assert code(s.create_channel, BOB, "public", None) == "bad_name"
    assert [c["name"] for c in s.list_public(CARA)] == ["general"]
    assert code(s.history, CARA, pub["id"]) == "forbidden"                   # public but not joined: no reading
    s.join(CARA, pub["id"])
    assert s.history(CARA, pub["id"])["messages"] == []
    assert s.list_public(CARA) == []
    priv = s.create_channel(ALICE, "private", "secret", ["bob"])
    assert code(s.get_channel, CARA, priv["id"]) == "no_such_channel"       # existence is not revealed
    assert code(s.join, CARA, priv["id"]) == "no_such_channel"
    assert code(s.add_member, BOB, priv["id"], "cara") == "forbidden"         # plain member of a private channel
    s.add_member(ALICE, priv["id"], "cara")
    s.set_role(ALICE, priv["id"], "cara", "admin")
    assert code(s.set_role, CARA, priv["id"], "bob", "admin") == "forbidden"
    s.add_member(CARA, priv["id"], "dan")                                     # admins invite
    assert code(s.remove_member, CARA, priv["id"], "alice") == "forbidden"    # admin cannot remove the owner
    s.remove_member(CARA, priv["id"], "dan")
    assert code(s.leave, ALICE, priv["id"]) == "last_owner"
    s.set_role(ALICE, priv["id"], "bob", "owner")
    s.leave(ALICE, priv["id"])
    assert code(s.get_channel, ALICE, priv["id"]) == "no_such_channel"


def test_direct_and_group_conversations(s):
    d = s.create_channel(ALICE, "direct", members=["bob"])
    again = s.create_channel(BOB, "direct", members=["alice"])
    assert d["created"] and not again["created"] and again["id"] == d["id"]
    assert code(s.create_channel, ALICE, "direct", members=["bob", "cara"]) == "bad_members"
    assert code(s.add_member, ALICE, d["id"], "cara") == "forbidden"
    assert code(s.leave, ALICE, d["id"]) == "forbidden"
    assert code(s.update_channel, ALICE, d["id"], {"archived": True}) == "forbidden"
    g = s.create_channel(ALICE, "group", members=["bob", "cara"])
    assert len(g["members"]) == 3 and code(s.create_channel, ALICE, "group", members=["bob"]) == "bad_members"
    assert code(s.post, DAN, g["id"], "hi") == "no_such_channel"
    s.leave(CARA, g["id"])
    m = s.post(ALICE, d["id"], "hello", topic="ignored")
    assert m["topic"] == ""                                                    # conversations have no topics


def test_messages_ordering_idempotency_threads_topics(room):
    s, cid = room
    ids = [s.post(ALICE if i % 2 else BOB, cid, f"m{i}", topic="t1" if i < 3 else "t2")["id"] for i in range(6)]
    assert ids == sorted(ids)
    got = s.history(BOB, cid)
    assert [m["body"] for m in got["messages"]] == [f"m{i}" for i in range(6)]
    assert [m["body"] for m in s.history(BOB, cid, topic="t2")["messages"]] == ["m3", "m4", "m5"]
    assert [m["id"] for m in s.history(BOB, cid, limit=2)["messages"]] == ids[-2:]
    assert [m["id"] for m in s.history(BOB, cid, before=ids[3], limit=2)["messages"]] == ids[1:3]
    assert [m["id"] for m in s.history(BOB, cid, after=ids[3])["messages"]] == ids[4:]
    assert [t["topic"] for t in s.topics(BOB, cid)] == ["t2", "t1"]
    a = s.post(ALICE, cid, "once", local_id="L-1")
    b = s.post(ALICE, cid, "once", local_id="L-1")
    assert b["duplicate"] and b["id"] == a["id"]
    assert sum(m["body"] == "once" for m in s.history(BOB, cid, limit=100)["messages"]) == 1
    assert s.post(BOB, cid, "once", local_id="L-1")["id"] != a["id"]          # ids are per sender
    r1 = s.post(BOB, cid, "reply", reply_to=a["id"])
    r2 = s.post(ALICE, cid, "reply to reply", reply_to=r1["id"])
    assert r2["thread_root"] == a["id"]
    assert [m["body"] for m in s.history(BOB, cid, thread=a["id"])["messages"]] == ["once", "reply", "reply to reply"]
    assert code(s.post, BOB, cid, "x", reply_to=99999) == "bad_reply"


def test_input_limits(room):
    s, cid = room
    assert code(s.post, ALICE, cid, "") == "bad_body"
    assert code(s.post, ALICE, cid, "   ") == "bad_body"
    assert code(s.post, ALICE, cid, "x" * 10_001) == "body_too_long"
    assert code(s.post, ALICE, cid, "a\x00b") == "bad_body"
    assert code(s.post, ALICE, cid, "x", topic="t" * 61) == "topic_too_long"
    assert code(s.post, ALICE, cid, "x", local_id="bad id!") == "bad_local_id"
    assert code(s.post, ALICE, cid, "x", attachments=["zz"]) == "bad_attachments"
    assert code(s.post, ALICE, cid, "x", attachments=["a" * 64]) == "bad_attachments"      # not uploaded by the sender
    assert code(s.post, ALICE, "1", "x") == "no_such_channel"
    flood = " ".join(f"@[bob{i}]" for i in range(11))
    assert code(s.post, ALICE, cid, flood) == "too_many_mentions"
    assert code(s.post, BOB, cid, "@[all] wake up") == "forbidden"            # only channel admins broadcast
    assert s.post(ALICE, cid, "@[all] meeting")["mentions"] == ["all"]
    assert s.post(ALICE, cid, "@[bob] and @[nobody-here]")["mentions"] == ["bob"]


def test_edit_history_delete_tombstone_reactions(room):
    s, cid = room
    m = s.post(BOB, cid, "first draft")
    assert code(s.edit, ALICE, m["id"], "hijack") == "forbidden"              # even the channel owner
    e = s.edit(BOB, m["id"], "second draft")
    assert e["body"] == "second draft" and e["edited_at"]
    assert [v["body"] for v in s.edit_history(ALICE, m["id"])] == ["first draft", "second draft"]
    s.react(ALICE, m["id"], "👍")
    s.react(ALICE, m["id"], "👍")
    s.react(BOB, m["id"], "ok")
    assert s.history(ALICE, cid)["messages"][0]["reactions"] == {"👍": ["alice"], "ok": ["bob"]}
    s.react(ALICE, m["id"], "👍", add=False)
    assert code(s.react, ALICE, m["id"], "a b") == "bad_emoji"
    assert code(s.delete, CARA, m["id"]) == "forbidden"
    s.delete(BOB, m["id"])
    t = s.history(ALICE, cid)["messages"][0]
    assert t["deleted"] and t["body"] is None and t["reactions"] == {} and t["sender"] == "bob"
    assert code(s.edit, BOB, m["id"], "again") == "no_such_message"
    other = s.post(BOB, cid, "owner may delete")
    s.delete(ALICE, other["id"])                                              # owner/admin of a named channel
    mine = s.post(ALICE, cid, "x")
    assert code(s.delete, BOB, mine["id"]) == "forbidden"
    many = s.post(ALICE, cid, "emoji")
    for i in range(20):
        s.react(BOB, many["id"], f"e{i}")
    assert code(s.react, BOB, many["id"], "e21") == "too_many_reactions"


def test_rate_limit_per_sender(room):
    s, cid = room
    now = [0.0]
    s.bucket = TokenBucket(3, 1.0, clock=lambda: now[0])
    for i in range(3):
        s.post(ALICE, cid, f"m{i}")
    assert code(s.post, ALICE, cid, "m3") == "rate_limited"
    assert s.post(BOB, cid, "someone else is fine")
    assert any(p["reason"] == "rate limit" for p in chat_trace("denied"))
    now[0] = 5.0
    s.post(ALICE, cid, "later")
    assert s.post(ALICE, cid, "dup?", local_id="k")["id"] and s.post(ALICE, cid, "dup?", local_id="k")["duplicate"]


def test_search_is_scoped_to_the_callers_channels(s):
    a = s.create_channel(ALICE, "private", "alice-only")
    b = s.create_channel(BOB, "public", "bob-room", ["alice"])
    s.post(ALICE, a["id"], "the Quarterly budget is secret")
    s.post(BOB, b["id"], "budget review on friday")
    assert [m["channel_id"] for m in s.search(ALICE, "budget")] == [b["id"], a["id"]]
    assert [m["channel_id"] for m in s.search(BOB, "budget")] == [b["id"]]
    assert s.search(CARA, "budget") == []
    assert code(s.search, BOB, "budget", channel_id=a["id"]) == "no_such_channel"
    assert s.search(ALICE, 'budget" OR secret*') == []                         # query syntax is neutralised: plain words, no error
    assert s.search(ALICE, "quarterly secret budget")[0]["channel_id"] == a["id"]
    m = s.post(ALICE, a["id"], "to be edited gizmo")
    assert s.search(ALICE, "gizmo")
    s.edit(ALICE, m["id"], "now about widgets")
    assert not s.search(ALICE, "gizmo") and s.search(ALICE, "widgets")
    s.delete(ALICE, m["id"])
    assert not s.search(ALICE, "widgets")
    assert s.search(ALICE, "!!!") == []


def test_search_fallback_without_fts5(tmp_path):
    st = Store(str(tmp_path / "nofts.db"), fts=False)
    s = service(store=st)
    assert not st.fts
    a = s.create_channel(ALICE, "private", "mine")
    b = s.create_channel(BOB, "private", "his")
    s.post(ALICE, a["id"], "100% sure_thing alpha")
    s.post(BOB, b["id"], "alpha but not yours")
    assert [m["channel_id"] for m in s.search(ALICE, "alpha")] == [a["id"]]
    assert s.search(ALICE, "sure_thing")[0]["body"].startswith("100%")
    assert s.search(ALICE, "nomatch") == []


def test_unread_counts_and_cursors(room):
    s, cid = room
    ids = [s.post(ALICE, cid, f"m{i}")["id"] for i in range(3)]
    snap = s.register(BOB)["snapshot"]["channels"][0]
    assert snap["unread"] == 3 and snap["last_message_id"] == ids[-1]
    assert s.register(ALICE)["snapshot"]["channels"][0]["unread"] == 0        # your own messages are read
    assert s.mark_read(BOB, cid, ids[0]) == ids[0]
    assert s.mark_read(BOB, cid, 0) == ids[0]                                 # never goes back
    assert s.register(BOB)["snapshot"]["channels"][0]["unread"] == 2
    assert s.mark_read(BOB, cid, 10 ** 6) == ids[-1]                           # nor past the end
    assert s.register(BOB)["snapshot"]["channels"][0]["unread"] == 0
    s.join(CARA, cid)
    assert s.register(CARA)["snapshot"]["channels"][0]["unread"] == 0          # joining does not hand you a backlog of unread


def test_pins_and_drafts(room):
    s, cid = room
    m = s.post(BOB, cid, "important")
    assert code(s.pin, BOB, m["id"]) == "forbidden"
    s.pin(ALICE, m["id"])
    assert [p["id"] for p in s.pins(BOB, cid)] == [m["id"]]
    s.pin(ALICE, m["id"], False)
    assert s.pins(BOB, cid) == []
    s.set_draft(BOB, cid, "plans", "half a thought")
    assert s.drafts(BOB)[0]["body"] == "half a thought" and s.drafts(ALICE) == []
    s.set_draft(BOB, cid, "plans", "")
    assert s.drafts(BOB) == []


def test_archived_channel(room):
    s, cid = room
    s.update_channel(ALICE, cid, {"archived": True})
    assert code(s.post, BOB, cid, "x") == "forbidden"
    assert s.history(BOB, cid)["messages"] == []
    assert code(s.update_channel, BOB, cid, {"archived": False}) == "forbidden"
    assert code(s.update_channel, ALICE, cid, {"owner": "x"}) == "bad_changes"
    assert code(s.update_channel, ALICE, cid, {"retention_days": 0}) == "bad_changes"


def test_retention_sweep_two_steps(room):
    s, cid = room
    now = [1_000_000.0]
    s.clock = lambda: now[0]
    old = s.post(ALICE, cid, "old news")
    s.update_channel(ALICE, cid, {"retention_days": 10})
    now[0] += 5 * DAY
    new = s.post(BOB, cid, "fresh")
    now[0] += 6 * DAY                                                          # old: 11 days, new: 6 days
    assert s.sweep(ORG, now=now[0]) == {"expired": 1, "purged": 0}
    got = {m["id"]: m for m in s.history(BOB, cid)["messages"]}
    assert got[old["id"]]["deleted"] and not got[old["id"]]["erased"] and not got[new["id"]]["deleted"]
    assert s.store.message(ORG, old["id"])["body"] == "old news"              # soft: still recoverable in the grace period
    assert not s.search(BOB, "old")
    now[0] += 31 * DAY
    assert s.sweep(ORG, now=now[0]) == {"expired": 1, "purged": 1}
    row = s.store.message(ORG, old["id"])
    assert row["body"] == "" and row["erased"] == 1                            # hard erase keeps only the tombstone
    assert [m["deleted"] for m in s.history(BOB, cid)["messages"]] == [True, True]
    assert chat_trace("retention.sweep")


def test_org_retention_default_and_settings_need_chat_admin(room):
    s, cid = room
    assert code(s.set_org_settings, ALICE, {"retention_days": 1}) == "forbidden"
    assert code(s.org_settings, ALICE) == "forbidden"
    assert code(s.set_org_settings, ADMIN, {"retention_days": 0}) == "bad_changes"
    assert code(s.set_org_settings, ADMIN, {"nope": 1}) == "bad_changes"
    now = [10 * DAY]
    s.clock = lambda: now[0]
    s.post(ALICE, cid, "x")
    s.set_org_settings(ADMIN, {"retention_days": 1, "purge_grace_days": 0})
    now[0] += 2 * DAY
    assert s.sweep(ORG, now=now[0])["expired"] == 1
    now[0] += 1
    assert s.sweep(ORG, now=now[0])["purged"] == 1


def test_legal_hold_blocks_delete_retention_and_erasure(room):
    s, cid = room
    now = [10 * DAY]
    s.clock = lambda: now[0]
    m = s.post(BOB, cid, "evidence")
    s.update_channel(ALICE, cid, {"retention_days": 1})
    assert code(s.set_legal_hold, ALICE, cid, True) == "forbidden"            # not chat_admin
    s.set_legal_hold(ADMIN, cid, True)
    assert code(s.delete, BOB, m["id"]) == "forbidden"
    assert code(s.delete, ALICE, m["id"]) == "forbidden"
    assert code(s.erase_message, ADMIN, m["id"]) == "forbidden"
    now[0] += 400 * DAY
    assert s.sweep(ORG, now=now[0]) == {"expired": 0, "purged": 0}
    assert s.erase_user(ADMIN, "bob")["messages_held_by_legal_hold"] == 1
    assert s.history(ALICE, cid)["messages"][0]["body"] == "evidence"
    s.set_legal_hold(ADMIN, cid, False)
    s.delete(ALICE, m["id"])


def test_export_channel_is_admin_only_and_traced(room):
    s, cid = room
    m = s.post(BOB, cid, "one")
    s.edit(BOB, m["id"], "two")
    s.post(ALICE, cid, "three")
    assert code(s.export_channel, ALICE, cid) == "forbidden"                   # not even the channel owner
    out = s.export_channel(ADMIN, cid)
    assert [x["body"] for x in out["messages"]] == ["two", "three"]
    assert out["messages"][0]["edits"][0]["body"] == "one"
    e = chat_trace("channel.export")[-1]
    assert e["caller"] == "root" and e["messages"] == 2 and len(e["export_sha256"]) == 64
    assert "two" not in trace_text()                                           # hashes and ids, not content
    assert code(s.export_channel, who("root2", org="other", roles=["chat_admin"]), cid) == "no_such_channel"
    assert code(s.export_channel, who("root", org="other", roles=["chat_admin"]), cid) == "wrong_organisation"   # an id is one org's


def test_user_export_and_erasure_for_dpdp(room):
    s, cid = room
    m = s.post(BOB, cid, "my personal note")
    s.edit(BOB, m["id"], "my edited personal note")
    s.react(BOB, m["id"], "ok")
    s.set_draft(BOB, cid, "t", "unsent")
    other = s.post(ALICE, cid, "alice speaking")
    own = s.export_user(BOB)
    assert own["messages"][0]["body"] == "my edited personal note" and own["drafts"] and own["channels"]
    assert code(s.export_user, ALICE, "bob") == "forbidden"
    assert s.export_user(ADMIN, "bob")["user"] == "bob"
    assert code(s.erase_user, BOB, "bob") == "forbidden"                       # an administrator carries erasure out
    res = s.erase_user(ADMIN, "bob")
    assert res == {"user": "bob", "messages_erased": 1, "messages_held_by_legal_hold": 0, "channels_left": 1,
                   "files_kept_by_legal_hold": 0, "reactions_kept_by_legal_hold": 0}
    row = s.store.message(ORG, m["id"])
    assert row["body"] == "" and row["erased"] == 1 and row["sender"].startswith("erased:") and row["sender"] != "bob"
    assert s.store.all("SELECT * FROM edits") == [] and s.store.all("SELECT * FROM drafts") == []
    assert s.store.all("SELECT * FROM reactions") == []
    assert s.store.role(cid, "bob") is None
    t = [x for x in s.history(ALICE, cid)["messages"]]
    assert t[0]["deleted"] and t[0]["erased"] and t[1]["body"] == "alice speaking"
    assert not s.search(ALICE, "personal")
    assert "personal" not in trace_text()
    assert code(s.erase_user, ADMIN, "nobody") == "no_such_user"
    assert other["id"] == t[1]["id"]


def test_assistant_ids_cannot_be_forged_by_a_caller(s):
    assert code(s.create_channel, who("assistant:velaris"), "public", "x") == "bad_identity"
    assert code(s.create_channel, ALICE, "direct", members=["assistant:rogue"]) == "unknown_assistant"
    d = s.create_channel(ALICE, "direct", members=["assistant:velaris"])
    assert d["created"]


def test_cross_organisation_is_refused(s, monkeypatch):
    ch = s.create_channel(ALICE, "public", "general")
    s.post(ALICE, ch["id"], "acme business")
    other = who("mallory", org="evil")
    assert code(s.get_channel, other, ch["id"]) == "no_such_channel"           # even without VELARIS_ORG set
    assert code(s.join, other, ch["id"]) == "no_such_channel"
    assert s.search(other, "acme") == []
    assert s.list_public(other) == []
    evil = s.create_channel(other, "public", "general")                          # names are per organisation
    assert evil["id"] != ch["id"]
    assert code(s.create_channel, who("alice", org="evil"), "public", "z") == "wrong_organisation"   # same id, other org
    monkeypatch.setenv("VELARIS_ORG", ORG)
    assert code(s.get_channel, other, ch["id"]) == "wrong_organisation"
    assert code(s.register, other) == "wrong_organisation"
    assert code(s.post, "not-a-caller", ch["id"], "x") == "unauthenticated"
    assert s.get_channel(ALICE, ch["id"])["id"] == ch["id"]
    assert any(p.get("step") == "enter" for p in chat_trace("denied"))


def test_every_denial_is_traced_with_ids_only(room):
    s, cid = room
    before = len(chat_trace("denied"))
    code(s.update_channel, BOB, cid, {"archived": True})
    code(s.post, CARA, cid, "x")
    d = chat_trace("denied")[before:]
    assert [(p["caller"], p["action"], p["channel"]) for p in d] == [("bob", "manage", cid), ("cara", "post", cid)]


def test_fails_closed_when_the_trace_cannot_be_written(room, monkeypatch):
    s, cid = room
    def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(trace, "append", broken)
    assert code(s.post, ALICE, cid, "unrecorded") == "audit_unavailable"
    monkeypatch.undo()
    assert s.history(ALICE, cid)["messages"] == []                              # not stored


def test_trace_never_holds_message_text(room):
    s, cid = room
    s.post(ALICE, cid, "the launch codes are swordfish-4411")
    s.search(ALICE, "swordfish")
    assert "swordfish" not in trace_text()
    assert chat_trace("message.post")[-1]["body_sha256"]


def _zip(part):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(part, "<x/>")
    return buf.getvalue()


def test_sniffing():
    sn = chat_files.sniff
    assert sn(b"\x89PNG\r\n\x1a\n....") == "image/png" and sn(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert sn(b"GIF89a..") == "image/gif" and sn(b"RIFF\x00\x00\x00\x00WEBPVP8 ") == "image/webp"
    assert sn(b"%PDF-1.7") == "application/pdf"
    assert sn(_zip("word/document.xml")) == chat_files.DOCX and sn(_zip("xl/workbook.xml")) == chat_files.XLSX
    assert sn(_zip("other.txt")) is None and sn(b"PK\x03\x04notazip") is None
    assert sn("héllo".encode()) == "text/plain" and sn(b"a,b\n1,2", "t.csv") == "text/csv"
    assert sn(b"\x00\x01\x02binary") is None and sn(b"\xff\xfe\xfa") is None and sn(b"") is None
    assert chat_files.clean_name("../../etc/passwd") == "etcpasswd" and chat_files.clean_name("") == "file"


def test_upload_download_and_attach(room):
    s, cid = room
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
    up = s.upload(ALICE, "pic.png", "image/png", png)
    assert up["content_type"] == "image/png" and len(up["hash"]) == 64
    assert s.upload(ALICE, "pic.png", None, png)["hash"] == up["hash"]
    assert s.upload(ALICE, "x.html", "text/html", b"<script>alert(1)</script>")["content_type"] == "text/plain"   # never served as html
    assert code(s.upload, ALICE, "x.svg", "image/svg+xml", b"<svg onload=alert(1)>") in ("type_mismatch",)
    assert code(s.upload, ALICE, "p.png", "application/pdf", png) == "type_mismatch"
    assert code(s.upload, ALICE, "e", None, b"") == "empty_file"
    assert code(s.upload, ALICE, "z", None, b"\x00\x00binary") == "unsupported_type"
    big = service(limits=Limits(max_file_bytes=100))
    assert code(big.upload, ALICE, "b.txt", None, b"x" * 101) == "file_too_large"
    assert code(s.download, BOB, up["hash"]) == "no_such_file"                 # not attached anywhere yet
    m = s.post(ALICE, cid, "see pic", attachments=[up["hash"]])
    assert m["attachments"] == [up["hash"]]
    meta, data = s.download(BOB, up["hash"])
    assert data == png and meta["content_type"] == "image/png"
    assert code(s.download, CARA, up["hash"]) == "no_such_file"                # not in the channel
    assert code(s.post, BOB, cid, "steal", attachments=[up["hash"]]) == "bad_attachments"
    s.delete(ALICE, m["id"])
    assert code(s.download, BOB, up["hash"]) == "no_such_file"                 # the message is gone
    assert s.download(ALICE, up["hash"])[1] == png                             # the uploader keeps it
    assert code(s.download, ALICE, "../etc/passwd") == "no_such_file"
    assert code(s.post, ALICE, cid, "x", attachments=[up["hash"]] * 6) == "bad_attachments"
    assert any("." not in str(p) for p in s.store.path.parent.glob("blobs/*/*"))
    for blob in s.store.path.parent.glob("blobs/*/*"):
        assert stat.S_IMODE(os.stat(blob).st_mode) == 0o600
    s.erase_user(ADMIN, "alice")
    assert not list(s.store.path.parent.glob("blobs/*/*"))


def test_unfurl_is_off_unless_allow_listed(room):
    import httpx
    from velaris.intel.web_fetch import Fetcher
    s, cid = room
    m = s.post(ALICE, cid, "read https://example.com/page and http://127.0.0.1/admin")
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<title> Example  page </title>")
    s.fetcher = Fetcher(transport=httpx.MockTransport(handler), resolver=lambda h: [h] if h[0].isdigit() else ["93.184.216.34"],
                        min_gap_s=0)
    assert s.unfurl(BOB, m["id"]) == [] and calls == []                         # disabled by default: nothing is fetched
    s.set_org_settings(ADMIN, {"unfurl_hosts": ["example.com", "127.0.0.1"]})
    out = s.unfurl(BOB, m["id"])
    assert out[0]["title"] == "Example page"
    assert len(out) == 1 and not any("127.0.0.1" in c for c in calls)         # an internal address never passes the fetch gate
    assert code(s.unfurl, CARA, m["id"]) == "forbidden"
