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
    c.row_factory = fieldseal.row_class("p", ("body",), "t")
    c.execute("CREATE TABLE t(id, body)")
    return c


def test_sealed_column_moved_between_rows_is_refused():
    c = _table()
    for i, text in ((1, "salary of asha"), (2, "lunch order")):
        c.execute("INSERT INTO t VALUES (?, ?)", (i, fieldseal.seal(text, "p", fieldseal.bind_for("t", "body", i))))
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


# ---- review findings: encoding, user text, migration robustness, mandatory file context ----------------------------------

def test_bind_encoding_is_unambiguous_and_names_the_table():
    a, b = fieldseal.bind_for("t", "c", "a.b", "c"), fieldseal.bind_for("t", "c", "a", "b.c")
    assert a != b and fieldseal.bind_for("t1", "c", 1) != fieldseal.bind_for("t2", "c", 1)
    assert a.startswith("b2:") and '"t"' in a                      # versioned, table inside


def test_user_text_that_looks_sealed_is_encrypted_like_any_other_text():
    assert fieldseal.unseal(fieldseal.seal("vlv1:abc", "p"), "p") == "vlv1:abc"
    assert "vlv1:abc" not in fieldseal.seal("vlv1:abc", "p")[5:]
    other = fieldseal.seal("secret", "p", fieldseal.bind_for("t", "body", 9))
    stored = fieldseal.seal(other, "p", fieldseal.bind_for("t", "body", 1))   # a sealed blob of another column, as USER text
    assert stored != other
    assert fieldseal.unseal(stored, "p", fieldseal.bind_for("t", "body", 1)) == other


def test_one_corrupt_row_does_not_stop_the_migration(monkeypatch):
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, body)")
    good = fieldseal.seal("one", "p")
    bad = good[:-8] + "AAAAAAAA"                                  # vlv1-shaped but it does not authenticate
    c.executemany("INSERT INTO t VALUES (?,?)", [(1, fieldseal.seal("zero", "p")), (2, bad), (3, good)])
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_PLAINTEXT", "1")
    vault.start_plaintext_migration()
    res = fieldseal.seal_existing(c, "t", ["body"], "p", key="id", batch=1)
    assert res == 2 and res.failed == [(2,)]
    c.row_factory = fieldseal.row_class("p", ("body",), "t")
    assert [c.execute("SELECT * FROM t WHERE id=?", (i,)).fetchone()["body"] for i in (1, 3)] == ["zero", "one"]
    raw = c.cursor()
    raw.row_factory = None
    assert raw.execute("SELECT body FROM t WHERE id=2").fetchone()[0] == bad     # left as it was, never blessed


def _old_log(name, records):
    path = agent_dir("BIND") / name
    for r in records:
        path.parent.mkdir(parents=True, exist_ok=True)
        import base64, json
        with open(path, "a") as f:
            f.write("VLV1:" + base64.b64encode(vault.seal_bytes(json.dumps(r).encode(), P)).decode() + "\n")
    return path


def test_log_migration_keeps_a_record_appended_while_it_runs(monkeypatch):
    from velaris.agentkit import state
    path = _old_log("race.jsonl", [{"n": 1}])
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_PLAINTEXT", "1")
    vault.start_plaintext_migration()
    real, calls = state._read_all, []

    def racing(p, enc):
        out = real(p, enc)
        if not calls:
            calls.append(1)
            append_line(p, {"n": 2}, encrypted=P)                  # another process appends between the read and the rewrite
        return out
    monkeypatch.setattr(state, "_read_all", racing)
    read_lines(path, encrypted=P)
    vault.end_plaintext_migration()
    assert [r["n"] for r in read_lines(path, encrypted=P)] == [1, 2]


def test_log_migration_refuses_to_rewrite_a_file_with_an_unreadable_line(monkeypatch):
    path = _old_log("torn.jsonl", [{"n": 1}])
    with open(path, "a") as f:
        f.write("{not json\n")
    before = path.read_bytes()
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_PLAINTEXT", "1")
    vault.start_plaintext_migration()
    with pytest.raises(vault.VaultError):
        read_lines(path, encrypted=P)
    assert path.read_bytes() == before                             # the file is untouched


def test_sealed_files_need_a_context_and_do_not_open_at_a_sibling_path(tmp_path):
    a, b = tmp_path / "a.bin", tmp_path / "b.bin"
    vault.write_sealed(a, b"alpha", "x", vault.path_context(a))
    vault.write_sealed(b, b"beta", "x", vault.path_context(b))
    with pytest.raises(TypeError):
        vault.read_sealed(a, "x")                                  # no optional context any more
    b.write_bytes(a.read_bytes())
    with pytest.raises(vault.VaultError):
        vault.read_sealed(b, "x", vault.path_context(b))
    vault.write_sealed_stream(a, [b"s" * 10], "x", vault.path_context(a))
    b.write_bytes(a.read_bytes())
    with pytest.raises(vault.VaultError):
        vault.read_sealed(b, "x", vault.path_context(b))


def test_hiring_upload_swapped_with_a_sibling_is_refused():
    from velaris.agentkit import hiring_intake
    d = agent_dir("SCREENING_FORMS") / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    p1, p2 = d / "sub-1.bin", d / "sub-2.bin"
    vault.write_sealed(p1, b"cv one", "hiring:SCREENING_FORMS", vault.path_context(p1))
    vault.write_sealed(p2, b"cv two", "hiring:SCREENING_FORMS", vault.path_context(p2))
    p2.write_bytes(p1.read_bytes())
    with pytest.raises(vault.VaultError):
        hiring_intake.file_b64(str(p2))


def test_old_stream_file_is_refused_outside_the_window_and_rebound_inside_it(tmp_path, monkeypatch):
    import os
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    p = tmp_path / "old.bin"
    nonce = os.urandom(12)
    ct = AESGCM(vault.derive_key("x")).encrypt(nonce, b"old audio", b"x|" + (0).to_bytes(8, "big") + b"L")   # VLS1 layout
    p.write_bytes(b"VLS1" + nonce + len(ct).to_bytes(4, "big") + ct)
    with pytest.raises(vault.PlaintextRefused):
        vault.read_sealed(p, "x", "old.bin")
    monkeypatch.setenv("VELARIS_VAULT_ALLOW_PLAINTEXT", "1")
    vault.start_plaintext_migration()
    assert vault.read_sealed(p, "x", "old.bin") == b"old audio"
    assert p.read_bytes()[:4] == vault.STREAM_MAGIC
    vault.end_plaintext_migration()
    assert vault.read_sealed(p, "x", "old.bin") == b"old audio"


def test_chat_file_name_moved_to_another_file_is_refused():
    from velaris.chat.files import file_name
    from velaris.tests.chat_support import ALICE, service
    s = service()
    s.upload(ALICE, "salary.csv", "text/csv", b"a,b\n1,2\n")
    s.upload(ALICE, "lunch.txt", "text/plain", b"lunch menu\n")
    rows = s.store.db.execute("SELECT * FROM files ORDER BY created_at, name").fetchall()
    assert len({file_name(r) for r in rows}) == 2
    s.store.db.execute("UPDATE files SET name=(SELECT name FROM files WHERE hash=?) WHERE hash=?", (rows[0]["hash"], rows[1]["hash"]))
    with pytest.raises(vault.VaultError):
        file_name(s.store.db.execute("SELECT * FROM files WHERE hash=?", (rows[1]["hash"],)).fetchone())
