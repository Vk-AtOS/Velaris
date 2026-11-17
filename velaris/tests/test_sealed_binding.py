"""Sealed data is bound to its location (KAN-69 SV2-06): a sealed file or column moved elsewhere does not open."""
import shutil
import sqlite3

import pytest

from velaris.agentkit.state import JsonState, append_line, read_lines
from velaris.core import fieldseal, sealed_sqlite as ss, vault
from velaris.intel.paths import agent_dir

P = "hr:BIND"


def test_json_state_file_swapped_to_another_file_of_the_same_agent_is_refused():
    a, b = JsonState("BIND", "a.json", encrypted=P), JsonState("BIND", "b.json", encrypted=P)
    a.save({"who": "a"})
    b.save({"who": "b"})
    shutil.copy(a.path, b.path)                       # the attacker overwrites b with the (valid, sealed) a
    with pytest.raises(vault.VaultError):
        b.load()
    assert a.load()["who"] == "a"


def test_json_state_of_an_older_release_is_bound_in_the_window_and_refused_outside(monkeypatch):
    s = JsonState("BIND", "old.json", encrypted=P)
    s.path.parent.mkdir(parents=True, exist_ok=True)
    s.path.write_bytes(vault.seal_bytes(b'{"who": "old"}', P))      # VLV1, as written before binding
    with pytest.raises(vault.PlaintextRefused):
        s.load()
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_PLAINTEXT", "1")
    vault.start_plaintext_migration()
    assert s.load()["who"] == "old"
    assert vault.is_bound(s.path.read_bytes())          # rebound at once
    vault.end_plaintext_migration()
    assert s.load()["who"] == "old"


def test_sealed_sqlite_file_swapped_to_another_store_is_refused(tmp_path):
    (tmp_path / "x").mkdir()
    (tmp_path / "y").mkdir()
    for d in "xy":
        c = ss.connect_sealed(tmp_path / d / "hr.db", P)
        c.execute("CREATE TABLE t(a)")
        c.execute("INSERT INTO t VALUES (?)", (d,))
        c.commit()
        c.close()
    shutil.copy(tmp_path / "x" / "hr.db", tmp_path / "y" / "hr.db")
    with pytest.raises(vault.VaultError):
        ss.connect_sealed(tmp_path / "y" / "hr.db", P)


def test_sealed_line_moved_to_another_log_is_refused():
    a, b = agent_dir("BIND") / "a.jsonl", agent_dir("BIND") / "b.jsonl"
    append_line(a, {"n": 1}, encrypted=P)
    shutil.copy(a, b)
    assert read_lines(a, encrypted=P) == [{"n": 1}]
    with pytest.raises(vault.VaultError):
        read_lines(b, encrypted=P)


def _table():
    c = sqlite3.connect(":memory:")
    c.row_factory = fieldseal.row_class("p", ("body",))
    c.execute("CREATE TABLE t(id, body)")
    return c


def test_sealed_column_moved_between_rows_is_refused():
    c = _table()
    for i, text in ((1, "salary of asha"), (2, "lunch order")):
        c.execute("INSERT INTO t VALUES (?, ?)", (i, fieldseal.seal(text, "p", fieldseal.bind_for("body", i))))
    assert c.execute("SELECT * FROM t WHERE id=1").fetchone()["body"] == "salary of asha"
    c.execute("UPDATE t SET body=(SELECT body FROM t WHERE id=1) WHERE id=2")      # copy row 1's ciphertext into row 2
    with pytest.raises(vault.VaultError):
        c.execute("SELECT * FROM t WHERE id=2").fetchone()["body"]


def test_unbound_value_in_a_bound_column_is_refused_then_bound_by_the_migration(monkeypatch):
    c = _table()
    c.execute("INSERT INTO t VALUES (1, ?)", (fieldseal.seal("old", "p"),))        # vlv1, as written before binding
    with pytest.raises(vault.PlaintextRefused):
        c.execute("SELECT * FROM t").fetchone()["body"]
    with pytest.raises(vault.PlaintextRefused):
        fieldseal.seal_existing(c, "t", ["body"], "p", key="id")                   # no window, no migration
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_PLAINTEXT", "1")
    vault.start_plaintext_migration()
    assert fieldseal.seal_existing(c, "t", ["body"], "p", key="id") == 1
    vault.end_plaintext_migration()
    assert c.execute("SELECT * FROM t").fetchone()["body"] == "old"


def test_chat_message_body_moved_to_another_message_is_refused():
    from velaris.tests.chat_support import ALICE, service
    s = service()
    ch = s.create_channel(ALICE, "public", "general", ["bob"])["id"]
    m1, m2 = s.post(ALICE, ch, "salary of asha")["id"], s.post(ALICE, ch, "lunch")["id"]
    s.store.db.execute("UPDATE messages SET body=(SELECT body FROM messages WHERE id=?) WHERE id=?", (m1, m2))
    with pytest.raises(vault.VaultError):
        s.store.one("SELECT * FROM messages WHERE id=?", (m2,))["body"]
