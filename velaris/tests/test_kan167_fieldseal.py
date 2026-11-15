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
