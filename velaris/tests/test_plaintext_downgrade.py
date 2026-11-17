"""A plaintext file planted where a sealed one is expected is refused everywhere (one root: vault.legacy_plaintext)."""
import json
import sqlite3

import pytest

from velaris.agentkit.state import JsonState, append_line, last_line, read_lines
from velaris.core import fieldseal, sealed_sqlite, vault


def _plant_db(p):
    c = sqlite3.connect(p)
    c.execute("CREATE TABLE t(a)")
    c.execute("INSERT INTO t VALUES ('forged')")
    c.commit()
    c.close()


def test_planted_plaintext_is_refused_by_every_sealed_reader(tmp_path):
    f = tmp_path / "blob"
    f.write_bytes(b"forged")
    with pytest.raises(vault.PlaintextRefused):
        vault.read_sealed(f, "x")

    j = tmp_path / "s.json"
    j.write_text(json.dumps({"admins": ["mallory"]}))
    with pytest.raises(vault.PlaintextRefused):
        JsonState("XP", path=j, encrypted="x").load()
    with pytest.raises(vault.PlaintextRefused):
        JsonState("XP", path=j, encrypted="x").update(lambda d: None)
    assert json.loads(j.read_bytes()) == {"admins": ["mallory"]}          # neither trusted nor sealed nor moved

    log = tmp_path / "e.jsonl"
    append_line(log, {"n": 1}, encrypted="x")
    with open(log, "a") as fh:
        fh.write(json.dumps({"n": 2, "forged": True}) + "\n")
    with pytest.raises(vault.PlaintextRefused):
        read_lines(log, encrypted="x")
    with pytest.raises(vault.PlaintextRefused):
        last_line(log, encrypted="x")

    db = tmp_path / "hr.db"
    _plant_db(db)
    with pytest.raises(vault.PlaintextRefused):
        sealed_sqlite.connect_sealed(db, "hr:TEST")
    assert db.read_bytes().startswith(b"SQLite format")

    with pytest.raises(vault.PlaintextRefused):
        fieldseal.unseal("forged message", "chat")
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE m(id INTEGER PRIMARY KEY, body TEXT)")
    c.execute("INSERT INTO m(body) VALUES ('forged')")
    with pytest.raises(vault.PlaintextRefused):
        fieldseal.seal_existing(c, "m", ["body"], "chat", key="id")
    assert c.execute("SELECT body FROM m").fetchone()[0] == "forged"      # not blessed by being sealed


def test_migration_window_seals_at_once_and_closes_for_good(tmp_path, monkeypatch, plaintext_migration):
    j = tmp_path / "s.json"
    j.write_text(json.dumps({"name": "Asha"}))
    assert JsonState("XP", path=j, encrypted="x").load() == {"name": "Asha"} and vault.is_sealed(j.read_bytes())
    db = tmp_path / "hr.db"
    _plant_db(db)
    sealed_sqlite.connect_sealed(db, "hr:TEST").close()
    assert vault.is_sealed(db.read_bytes())

    vault.end_plaintext_migration()                    # the switch left on by mistake no longer opens anything
    j2 = tmp_path / "late.json"
    j2.write_text("{}")
    with pytest.raises(vault.PlaintextRefused):
        JsonState("XP", path=j2, encrypted="x").load()
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_PLAINTEXT", "true")           # only the exact value "1" counts
    assert vault.plaintext_allowed() is False


def test_window_needs_a_token_only_the_key_holder_can_make(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_PLAINTEXT", "1")
    assert vault.plaintext_allowed() is False                              # switch alone: closed, nothing to delete
    tok = vault._data_dir() / vault.OPEN_TOKEN
    tok.parent.mkdir(parents=True, exist_ok=True)
    tok.write_text(json.dumps({"expires": 4102444800, "mac": "0" * 64}))   # a data-directory writer forges one
    assert vault.plaintext_allowed() is False
    vault.start_plaintext_migration()
    assert vault.plaintext_allowed() is True
    good = json.loads(tok.read_text())
    tok.write_text(json.dumps({"expires": good["expires"] + 10_000, "mac": good["mac"]}))   # extends it
    assert vault.plaintext_allowed() is False
    tok.write_text(json.dumps({"expires": 1, "mac": vault._token_mac(1)}))  # genuine but expired
    assert vault.plaintext_allowed() is False
    vault.start_plaintext_migration()
    monkeypatch.setenv("VELARIS_VAULT_KEY", vault.new_key())              # token made under another key
    assert vault.plaintext_allowed() is False


@pytest.mark.parametrize("v", ["", "plain", b"plain", 5, 1.5])
def test_unseal_refuses_everything_that_is_not_a_sealed_text(v):
    with pytest.raises(vault.PlaintextRefused):
        fieldseal.unseal(v, "chat")
    assert fieldseal.unseal(None, "chat") is None
    assert fieldseal.unseal(fieldseal.seal("", "chat"), "chat") == ""      # '' is valid only sealed
    with pytest.raises(TypeError):
        fieldseal.seal(5, "chat")


def test_old_empty_strings_are_sealed_silently_but_text_is_not():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE m(id INTEGER PRIMARY KEY, body TEXT)")
    c.execute("INSERT INTO m(body) VALUES ('')")
    assert fieldseal.seal_existing(c, "m", ["body"], "chat", key="id") == 1
    assert fieldseal.unseal(c.execute("SELECT body FROM m").fetchone()[0], "chat", fieldseal.bind_for("body", 1)) == ""
    c.execute("INSERT INTO m(body) VALUES (7)")
    with pytest.raises(vault.PlaintextRefused):
        fieldseal.seal_existing(c, "m", ["body"], "chat", key="id")
