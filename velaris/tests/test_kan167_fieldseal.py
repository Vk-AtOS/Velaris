"""KAN-167: memory and docs are encrypted at rest (column level); remember() holds no lock across a model call."""
import sqlite3

import pytest

from velaris.core import fieldseal, vault
from velaris.intel.docs import DocStore
from velaris.intel.llm import FakeLLM
from velaris.intel.memory import MemoryStore
from velaris.intel.paths import data_dir


def test_roundtrip_and_blind_token_helpers():
    s = fieldseal.seal("hello Asha", "x")
    assert s.startswith("vlv1:") and "Asha" not in s and fieldseal.unseal(s, "x") == "hello Asha"
    assert fieldseal.seal(s, "x") == s and fieldseal.unseal("plain", "x") == "plain"
    with pytest.raises(vault.VaultError):
        fieldseal.unseal(s, "other-store")
    assert fieldseal.blind_tokens("Hello hello WORLD", "m") == fieldseal.blind_tokens("hello world", "m")
    assert "hello" not in fieldseal.blind_tokens("hello", "m")


def test_row_class_unseals_by_column_name_for_key_dict_and_iteration():
    c = sqlite3.connect(":memory:")
    c.row_factory = fieldseal.row_class("p", ("body",))
    c.execute("CREATE TABLE t(id, body)")
    c.execute("INSERT INTO t VALUES (1, ?)", (fieldseal.seal("secret", "p"),))
    r = c.execute("SELECT * FROM t").fetchone()
    assert r["body"] == "secret" and r[1] == "secret" and dict(r) == {"id": 1, "body": "secret"} and tuple(r) == (1, "secret")


def test_plaintext_from_older_release_is_sealed_at_open_and_old_pages_are_vacuumed():
    db = data_dir() / "mem_old.db"
    c = sqlite3.connect(db)
    c.executescript("CREATE TABLE memories(id TEXT PRIMARY KEY, text TEXT, embedding TEXT)")
    c.execute("INSERT INTO memories VALUES ('1', 'PAN ABCDE1234F belongs to Asha', '[1.0]')")
    c.commit()
    assert fieldseal.seal_existing(c, "memories", ["text", "embedding"], "memory", key="id") == 1
    c.close()
    assert b"ABCDE1234F" not in db.read_bytes()


def test_docs_store_is_sealed_in_the_file_and_still_searchable():
    llm = FakeLLM(lambda p, m: "x")
    store = DocStore(llm)
    store.ingest("policy.txt", b"Leave policy: Asha Verma gets 12 days of casual leave.", scope="acme")
    raw = (data_dir() / "docs.db").read_bytes()
    assert b"casual leave" not in raw and b"Asha" not in raw
    assert any("casual leave" in p.text for p in store.search("casual leave", scope="acme"))


def test_remember_does_not_hold_the_lock_across_the_model_call():
    mem = MemoryStore(FakeLLM(lambda p, m: '{"action": "ADD", "target": null}'))
    held = []
    real = mem._decide

    def spy(fact, related):
        held.append(mem._lock.locked())
        return real(fact, related)
    mem._decide = spy
    mem.remember("Asha Verma lives in Chennai and works on payroll.", scope="acme")
    mem.remember("Asha Verma lives in Chennai and works on payroll systems.", scope="acme")
    assert held and not any(held)


def _chat_file_bytes(svc):
    svc.store.db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return svc.store.path.read_bytes() + (svc.store.path.parent / (svc.store.path.name + "-wal")).read_bytes() \
        if (svc.store.path.parent / (svc.store.path.name + "-wal")).exists() else svc.store.path.read_bytes()


@pytest.mark.parametrize("fts", [True, False])
def test_chat_text_is_sealed_in_the_file_and_search_still_works(tmp_path, fts):
    from velaris.chat.store import Store
    from velaris.tests.chat_support import ALICE, service
    svc = service(store=Store(str(tmp_path / f"c{fts}.db"), fts=fts))
    ch = svc.create_channel(ALICE, "private", "mine")
    m = svc.post(ALICE, ch["id"], "the quarterly zebra payroll figures")
    svc.edit(ALICE, m["id"], "the quarterly giraffe payroll figures")
    raw = _chat_file_bytes(svc)
    for word in (b"zebra", b"giraffe", b"payroll"):
        assert word not in raw
    assert svc.search(ALICE, "giraffe")[0]["body"] == "the quarterly giraffe payroll figures"
    assert svc.search(ALICE, "zebra") == [] and svc.edit_history(ALICE, m["id"])[0]["body"].startswith("the quarterly zebra")
    assert svc.store.fts is fts


def test_chat_database_of_an_older_release_is_sealed_and_reindexed_once(tmp_path):
    import sqlite3
    from velaris.chat.store import SCHEMA, Store
    from velaris.tests.chat_support import ALICE, service
    path = tmp_path / "old.db"
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    c.execute("INSERT INTO channels(org, kind, name, created_by, created_at) VALUES('acme','private','old','alice',1)")
    c.execute("INSERT INTO members VALUES(1,'alice','owner',1,0)")
    c.execute("INSERT INTO messages(org, channel_id, topic, sender, body, created_at) VALUES('acme',1,'','alice','legacy rhinoceros text',1)")
    c.execute("CREATE VIRTUAL TABLE msg_fts USING fts5(body, tokenize='unicode61')")
    c.execute("INSERT INTO msg_fts(rowid, body) VALUES(1,'legacy rhinoceros text')")
    c.commit()
    c.close()
    svc = service(store=Store(str(path)))
    assert b"rhinoceros" not in path.read_bytes() and svc.search(ALICE, "rhinoceros")[0]["body"] == "legacy rhinoceros text"


def test_mail_text_attachments_and_search_index_are_sealed_but_search_and_threading_work():
    from velaris.mail.mime import parse_message
    from velaris.tests.mail_helpers import ALICE, make_world, raw_mail
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    put = lambda **kw: store.deliver(mb["id"], parse_message(raw_mail(**kw), fallback_ts=store.clock()), received=store.clock())
    a = put(mid="a@x", subject="Salary revision for Asha", body="the zebra budget is confidential", frm="boss@ext.org")
    put(mid="b@x", subject="Re: Salary revision for Asha", extra="In-Reply-To: <a@x>\r\n")
    store._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    raw = store.path.read_bytes()
    for word in (b"Salary", b"zebra", b"confidential", b"boss@ext.org", b"salary"):
        assert word not in raw
    assert [m["subject"] for m in store.list_messages(ALICE, mb["id"], q="zebra")["messages"]] == ["Salary revision for Asha"]
    assert store.list_messages(ALICE, mb["id"], q="conf")["total"] == 1          # prefix of 4 letters
    assert store.row(mb["id"], a)["thread_id"] == store.row(mb["id"], put(mid="c@x", subject="RE: salary revision for asha"))["thread_id"]
    store.fts = False                                                             # the no-FTS fallback decrypts and filters
    assert store.list_messages(ALICE, mb["id"], q="zebra")["total"] == 1


def test_mail_database_of_an_older_release_is_sealed_and_reindexed_once(tmp_path):
    import sqlite3
    from velaris.mail import db as maildb
    path = tmp_path / "old_mail.db"
    c = sqlite3.connect(path)
    c.executescript(maildb.SCHEMA)
    c.execute("INSERT INTO mailbox VALUES('m1','acme','a@acme.com','alice','user',1000000,'','{}',0,1)")
    c.execute("INSERT INTO folder VALUES('f1','m1','acme','Inbox','inbox')")
    c.execute("INSERT INTO thread VALUES('t1','m1','acme','legacy giraffe subject',1)")
    c.execute("INSERT INTO message(id, org, mailbox_id, folder_id, thread_id, message_id, subject, received_ts, size, body_text, source) "
              "VALUES('x1','acme','m1','f1','t1','a@x','legacy giraffe subject',1,10,'legacy giraffe body','inbound')")
    c.execute("CREATE VIRTUAL TABLE msg_fts USING fts5(subject, body, people)")
    c.execute("INSERT INTO msg_fts(rowid, subject, body, people) VALUES(1,'legacy giraffe subject','legacy giraffe body','')")
    c.commit()
    c.close()
    store = maildb.Database(str(path))
    assert b"giraffe" not in path.read_bytes()
    assert store.one("SELECT subject FROM message WHERE id='x1'")["subject"] == "legacy giraffe subject"
    from velaris.core import fieldseal
    t = " ".join('"' + x + '"' for x in fieldseal.blind_query(["giraffe"], "mail"))
    assert store.one("SELECT rowid FROM msg_fts WHERE msg_fts MATCH ?", (t,)) is not None
