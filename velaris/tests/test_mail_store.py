"""The mailbox store: threading, flags, search, attachments, quotas, retention, hold, delegation, erasure, org isolation."""
import os
import stat

import pytest

from velaris.core.access import Caller
from velaris.mail.common import MailError
from velaris.mail.mime import parse_message
from velaris.tests.mail_helpers import ADMIN, ALICE, BOB, CAROL, ORG, make_world, raw_mail


def put(store, mb, **kw):
    return store.deliver(mb["id"], parse_message(raw_mail(**kw), fallback_ts=store.clock()), received=store.clock())


def test_files_are_owner_only_and_wal(tmp_path):
    store, *_ = make_world()
    assert stat.S_IMODE(os.stat(store.path).st_mode) & 0o077 == 0
    assert store.one("PRAGMA journal_mode")[0] == "wal"
    assert stat.S_IMODE(os.stat(store.path.parent).st_mode) & 0o077 == 0


def test_threading_by_references_subject_fallback_and_out_of_order():
    store, _, _, clock, _, boxes = make_world()
    mb = boxes["alice"]
    a = put(store, mb, mid="a@x", subject="Plan")
    b = put(store, mb, mid="b@x", subject="Re: Plan", extra="In-Reply-To: <a@x>\r\nReferences: <a@x>\r\n")
    c = put(store, mb, mid="c@x", subject="RE: plan", extra="")                       # no headers, reply subject: fallback
    d = put(store, mb, mid="d@x", subject="Plan")                                       # same subject but not a reply: new thread
    e = put(store, mb, mid="e@x", subject="Re: Other", extra="In-Reply-To: <later@x>\r\n")
    f = put(store, mb, mid="later@x", subject="Other thing")                           # arrives after its reply
    t = lambda m: store.row(mb["id"], m)["thread_id"]       # noqa: E731
    assert t(a) == t(b) == t(c) and t(d) != t(a) and t(e) == t(f)
    thread = store.get_thread(ALICE, mb["id"], t(a))
    assert [m["id"] for m in thread["messages"]][:1] == [a] and len(thread["messages"]) == 3


def test_dedup_by_message_id_per_source_and_flags_labels_move():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    m = put(store, mb, mid="dup@x")
    assert put(store, mb, mid="dup@x") is None
    out = store.update_message(ALICE, mb["id"], m, seen=True, flagged=True, add_labels=["work", "urgent"], folder="Archive")
    assert out["seen"] and out["flagged"] and out["labels"] == ["urgent", "work"] and out["folder_role"] == "archive"
    assert store.list_messages(ALICE, mb["id"], folder="archive", label="work")["total"] == 1
    assert store.list_messages(ALICE, mb["id"], folder="inbox")["total"] == 0
    with pytest.raises(MailError):
        store.update_message(ALICE, mb["id"], m, add_labels=["x" * 51])
    fid = store.create_folder(ALICE, mb["id"], "Projects")["id"]
    assert store.update_message(ALICE, mb["id"], m, folder="projects")["folder"] == "Projects"
    assert store.folders(ALICE, mb["id"])[-1]["total"] == 1 and fid


@pytest.mark.parametrize("fts", [True, False])
def test_search_with_fts_and_like_fallback(monkeypatch, fts):
    store, _, _, _, _, boxes = make_world()
    store.fts = store.fts and fts
    mb = boxes["alice"]
    put(store, mb, mid="s1@x", subject="Quarterly budget review", body="numbers for the budget meeting", frm="boss@ext.org")
    put(store, mb, mid="s2@x", subject="Lunch", body="pizza at noon")
    r = store.list_messages(ALICE, mb["id"], q="budget")
    assert [m["subject"] for m in r["messages"]] == ["Quarterly budget review"]
    assert store.list_messages(ALICE, mb["id"], q="boss")["total"] == 1
    assert store.list_messages(ALICE, mb["id"], q="piz")["total"] == 1
    assert store.list_messages(ALICE, mb["id"], q="100%_")["total"] == 0                # wildcards are data, not patterns
    with pytest.raises(MailError):
        store.list_messages(ALICE, mb["id"], q="!!!")
    store.purge([r["messages"][0]["id"]])
    assert store.list_messages(ALICE, mb["id"], q="budget")["total"] == 0            # gone from the index too


def test_attachments_by_hash_dedup_and_collected_when_unreferenced():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    att = (b"Content-Type: multipart/mixed; boundary=B\r\nFrom: a@x.com\r\nMessage-ID: <%s>\r\n\r\n--B\r\nContent-Type: text/plain\r\n\r\nt\r\n--B\r\n"
           b'Content-Type: application/pdf\r\nContent-Disposition: attachment; filename="f.pdf"\r\nContent-Transfer-Encoding: base64\r\n\r\nSGVsbG8=\r\n--B--\r\n')
    ids = [store.deliver(mb["id"], parse_message(att.replace(b"%s", n)), received=1.0) for n in (b"1@x", b"2@x")]
    sha = store.get_message(ALICE, mb["id"], ids[0])["attachment_list"][0]["sha256"]
    meta, data = store.attachment(ALICE, mb["id"], ids[0], sha)
    assert data == b"Hello" and meta["name"] == "f.pdf"
    assert len(list(store.blob_dir.rglob(sha))) == 1                                 # stored once
    store.purge([ids[0]])
    assert store.get_blob(sha) == b"Hello"                                           # still referenced
    store.purge([ids[1]])
    with pytest.raises(MailError):
        store.get_blob(sha)
    with pytest.raises(MailError):
        store.attachment(ALICE, mb["id"], ids[0], "0" * 64)


def test_blob_integrity_is_checked_on_read():
    store, *_ = make_world()
    sha = __import__("hashlib").sha256(b"abc").hexdigest()
    store.put_blob(sha, b"abc")
    path = store._blob_path(sha)
    os.chmod(path, 0o600)
    path.write_bytes(b"tampered")
    with pytest.raises(MailError) as e:
        store.get_blob(sha)
    assert e.value.code == "corrupt"
    with pytest.raises(MailError):
        store.put_blob(sha, b"different")


def test_quota_refuses_over_limit_and_admin_can_raise_it():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    store.run("UPDATE mailbox SET quota_bytes=? WHERE id=?", (600, mb["id"]))
    put(store, mb, mid="q1@x", body="x" * 300)
    with pytest.raises(MailError) as e:
        put(store, mb, mid="q2@x", body="y" * 500)
    assert e.value.code == "quota_exceeded" and e.value.status == 552
    with pytest.raises(MailError):
        store.set_quota(ALICE, mb["id"], 10 * 1024 * 1024)                            # owners cannot raise their own quota
    assert store.set_quota(ADMIN, mb["id"], 10 * 1024 * 1024)["quota_bytes"] == 10 * 1024 * 1024
    put(store, mb, mid="q2@x", body="y" * 500)


def test_soft_delete_restore_and_permanent_delete_rules():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    m = put(store, mb, mid="d@x")
    assert store.delete_message(ALICE, mb["id"], m) == {"deleted": "soft"}
    got = store.get_message(ALICE, mb["id"], m)
    assert got["deleted"] and got["folder_role"] == "trash"
    assert store.restore_message(ALICE, mb["id"], m)["folder_role"] == "inbox"
    with pytest.raises(MailError) as e:
        store.delete_message(ALICE, mb["id"], m, permanent=True)                      # not in trash yet
    assert e.value.code == "not_in_trash"
    store.delete_message(ALICE, mb["id"], m)
    assert store.delete_message(ALICE, mb["id"], m, permanent=True) == {"deleted": "permanent"}
    with pytest.raises(MailError):
        store.get_message(ALICE, mb["id"], m)


def test_legal_hold_blocks_purge_retention_and_erasure():
    store, _, _, clock, _, boxes = make_world()
    mb = boxes["alice"]
    m1, m2 = put(store, mb, mid="h1@x"), put(store, mb, mid="h2@x")
    store.set_hold(ADMIN, mb["id"], True, [m1])
    for m in (m1, m2):
        store.delete_message(ALICE, mb["id"], m)
    with pytest.raises(MailError) as e:
        store.delete_message(ALICE, mb["id"], m1, permanent=True)
    assert e.value.code == "legal_hold"
    clock.advance(40 * 86400)
    assert store.retention_run(ADMIN)["trash"] == 1                                    # m2 only
    store.get_message(ALICE, mb["id"], m1)
    with pytest.raises(MailError) as e:
        store.erase_mailbox(ALICE, mb["id"])
    assert e.value.code == "legal_hold"
    store.set_hold(ADMIN, mb["id"], False, [m1])
    store.set_hold(ADMIN, mb["id"], True)                                               # whole-mailbox hold
    with pytest.raises(MailError):
        store.delete_message(ALICE, mb["id"], m1, permanent=True)
    with pytest.raises(MailError):
        store.set_hold(ALICE, mb["id"], False)                                          # only an admin lifts a hold


def test_retention_by_age_and_spam_folder():
    store, _, _, clock, _, boxes = make_world(settings={"retention_days": 90, "spam_retention_days": 7})
    mb = boxes["alice"]
    old = put(store, mb, mid="old@x")
    clock.advance(10 * 86400)
    spam = store.deliver(mb["id"], parse_message(raw_mail(mid="sp@x")), folder_role="quarantine", received=clock())
    clock.advance(8 * 86400)
    assert store.retention_run(ADMIN)["spam"] == 1
    clock.advance(100 * 86400)
    assert store.retention_run(ADMIN)["age"] == 1
    assert store.one("SELECT COUNT(*) FROM message")[0] == 0 and old and spam


def test_delegation_rights_and_recording():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    m = put(store, mb, mid="dg@x")
    with pytest.raises(MailError) as e:
        store.get_message(BOB, mb["id"], m)
    assert e.value.status == 404                                                        # no probing of other people's mailboxes
    store.set_delegate(ALICE, mb["id"], "bob", ["read"])
    assert store.get_message(BOB, mb["id"], m)["id"] == m
    with pytest.raises(MailError) as e:
        store.update_message(BOB, mb["id"], m, seen=True)
    assert e.value.status == 403
    store.set_delegate(ALICE, mb["id"], "bob", ["read", "send"])
    store.update_message(BOB, mb["id"], m, seen=True)
    assert [b["access"] for b in store.mailboxes_for(BOB) if b["id"] == mb["id"]] == ["delegate"]
    assert store.delegates(ALICE, mb["id"])[0]["user_id"] == "bob"
    store.remove_delegate(ALICE, mb["id"], "bob")
    with pytest.raises(MailError):
        store.get_message(BOB, mb["id"], m)
    with pytest.raises(MailError):
        store.set_delegate(ALICE, mb["id"], "alice", ["read"])                          # the owner is not a delegate of themselves


def test_cross_org_refusal_everywhere(monkeypatch):
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    m = put(store, mb, mid="co@x")
    mallory = Caller("alice", "evilcorp")                      # same user id, another organisation
    for call in (lambda: store.get_message(mallory, mb["id"], m), lambda: store.list_messages(mallory, mb["id"]),
                 lambda: store.folders(mallory, mb["id"]), lambda: store.export_mailbox(mallory, mb["id"]),
                 lambda: store.erase_mailbox(mallory, mb["id"]), lambda: store.set_delegate(mallory, mb["id"], "x", ["read"])):
        with pytest.raises(MailError) as e:
            call()
        assert e.value.status == 404
    assert store.mailboxes_for(mallory) == []
    with pytest.raises(MailError):
        store.get_message(None, mb["id"], m)                    # no caller at all
    monkeypatch.setenv("VELARIS_ORG", ORG)                      # deployment org set: another org is refused before any lookup
    with pytest.raises(MailError) as e:
        store.mailboxes_for(mallory)
    assert e.value.code == "wrong_organisation"
    assert store.one("SELECT org FROM message WHERE id=?", (m,))["org"] == ORG          # records carry the org


def test_export_and_erasure_remove_everything_but_audit_holds_ids_only():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    put(store, mb, mid="ex@x", subject="secret subject", frm="friend@ext.org")
    out = store.export_mailbox(ALICE, mb["id"])
    assert out["messages"][0]["subject"] == "secret subject" and not out["truncated"]
    store.set_mailbox_settings(ALICE, mb["id"], {"signature": "Alice"})
    assert store.erase_mailbox(ALICE, mb["id"]) == {"erased": True, "messages": 1}
    assert store.one("SELECT COUNT(*) FROM mailbox WHERE id=?", (mb["id"],))[0] == 0
    assert store.one("SELECT COUNT(*) FROM message")[0] == 0 and store.one("SELECT COUNT(*) FROM folder WHERE mailbox_id=?", (mb["id"],))[0] == 0
    from velaris.intel import trace
    blob = "".join(str(e["payload"]) for e in trace.entries() if e["actor"] == "mail")
    assert "secret subject" not in blob and "friend@ext.org" not in blob and "alice@acme.com" not in blob


def test_org_settings_validation_and_admin_only():
    store, *_ = make_world()
    with pytest.raises(MailError):
        store.set_org_settings(ALICE, {"undo_window_s": 5})
    for bad in ({"nope": 1}, {"undo_window_s": 9999}, {"local_domains": ["not a domain"]}, {"autoreply_external": "yes"}, {"spam_threshold": 0}, {}):
        with pytest.raises(MailError):
            store.set_org_settings(ADMIN, bad)
    s = store.set_org_settings(ADMIN, {"undo_window_s": 10, "allowlisted_domains": ["Partner.COM"]})
    assert s["undo_window_s"] == 10 and s["allowlisted_domains"] == ["partner.com"] and s["local_domains"] == ["acme.com"]


def test_vacation_and_signature_validation():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    with pytest.raises(MailError):
        store.set_mailbox_settings(ALICE, mb["id"], {"vacation": {"enabled": True}})          # a body is required
    with pytest.raises(MailError):
        store.set_mailbox_settings(ALICE, mb["id"], {"vacation": {"enabled": True, "body": "x", "window_days": 99}})
    out = store.set_mailbox_settings(ALICE, mb["id"], {"vacation": {"enabled": True, "body": "away", "window_days": 3}})
    assert out["vacation"]["window_days"] == 3


def test_mail_admin_cannot_export_someone_elses_mailbox():
    """KAN-69 SV2-02: export returns every message of a mailbox; a mail_admin who is not its owner must not get it."""
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    put(store, mb, mid="adm@x", subject="private subject")
    with pytest.raises(MailError) as e:
        store.export_mailbox(ADMIN, mb["id"])
    assert e.value.status == 403
    assert store.export_mailbox(ALICE, mb["id"])["messages"]            # the owner still can


def test_legal_hold_export_needs_a_second_approver_and_is_off_by_default():
    """KAN-69 SV2-02: owner-only by default; with legal_export on, a mail_admin exports once after another person approves."""
    store, _, _, clock, _, boxes = make_world()
    mb, admin2 = boxes["alice"], Caller("admin2", ORG, frozenset({"mail_admin"}))
    put(store, mb, mid="l1@x", subject="held")
    with pytest.raises(MailError):
        store.request_legal_export(ADMIN, mb["id"], "court order 42, matter X")            # off by default
    store.set_org_settings(ADMIN, {"legal_export": True})
    with pytest.raises(MailError):
        store.request_legal_export(ALICE, mb["id"], "court order 42, matter X")            # not an administrator
    with pytest.raises(MailError):
        store.request_legal_export(ADMIN, mb["id"], "short")                               # a reason is required
    rid = store.request_legal_export(ADMIN, mb["id"], "court order 42, matter X")["id"]
    for bad in (lambda: store.export_mailbox(ADMIN, mb["id"]),                              # no request cited
                lambda: store.export_mailbox(ADMIN, mb["id"], legal_request=rid),           # not approved yet
                lambda: store.decide_legal_export(ADMIN, rid, True),                        # the requester cannot approve
                lambda: store.decide_legal_export(BOB, rid, True)):                         # nor can a plain member
        with pytest.raises(MailError) as e:
            bad()
        assert e.value.status == 403
    assert store.decide_legal_export(admin2, rid, True)["state"] == "approved"
    with pytest.raises(MailError):
        store.export_mailbox(admin2, mb["id"], legal_request=rid)                           # only for the requester
    assert store.export_mailbox(ADMIN, mb["id"], legal_request=rid)["messages"]
    with pytest.raises(MailError):
        store.export_mailbox(ADMIN, mb["id"], legal_request=rid)                            # single use
    other = store.request_legal_export(ADMIN, mb["id"], "court order 43, matter Y")["id"]
    store.decide_legal_export(admin2, other, True)
    clock.advance(25 * 3600)
    with pytest.raises(MailError):
        store.export_mailbox(ADMIN, mb["id"], legal_request=other)                          # expired
    rej = store.request_legal_export(ADMIN, mb["id"], "court order 44, matter Z")["id"]
    store.decide_legal_export(CAROL, rej, False)
    with pytest.raises(MailError):
        store.export_mailbox(ADMIN, mb["id"], legal_request=rej)
