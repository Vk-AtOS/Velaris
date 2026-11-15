"""KAN-107/167: sqlite personal-data stores are encrypted at rest (whole-file seal, key outside VELARIS_DATA)."""
import sqlite3

import pytest

from velaris.core import sealed_sqlite as ss
from velaris.core import vault


def test_file_holds_no_plaintext_and_data_survives_reopen(tmp_path):
    p = tmp_path / "hr.db"
    c = ss.connect_sealed(p, "hr:TEST")
    c.execute("CREATE TABLE t(name TEXT)")
    c.execute("INSERT INTO t VALUES ('Asha Verma PAN ABCDE1234F')")
    c.commit()
    raw = p.read_bytes()
    assert vault.is_sealed(raw) and b"Asha" not in raw and b"SQLite format" not in raw
    c.close()
    assert ss.connect_sealed(p, "hr:TEST").execute("SELECT name FROM t").fetchone()[0].startswith("Asha")


def test_context_manager_commit_and_close_flush(tmp_path):
    p = tmp_path / "hr.db"
    c = ss.connect_sealed(p, "hr:TEST")
    c.execute("CREATE TABLE t(a)")
    with c:
        c.execute("INSERT INTO t VALUES (1)")
    c2 = ss.connect_sealed(p, "hr:TEST")
    assert c2.execute("SELECT a FROM t").fetchone()[0] == 1


def test_missing_key_wrong_purpose_and_tamper_fail_closed(tmp_path, monkeypatch):
    p = tmp_path / "hr.db"
    c = ss.connect_sealed(p, "hr:TEST")
    c.execute("CREATE TABLE t(a)")
    c.commit()
    with pytest.raises(vault.VaultError):
        ss.connect_sealed(p, "hr:OTHER")                    # a file cannot be swapped between stores
    blob = bytearray(p.read_bytes())
    blob[-1] ^= 1
    p.write_bytes(bytes(blob))
    with pytest.raises(vault.VaultError):
        ss.connect_sealed(p, "hr:TEST")
    monkeypatch.delenv("VELARIS_VAULT_KEY")
    with pytest.raises(vault.VaultKeyError):
        ss.connect_sealed(tmp_path / "new.db", "hr:TEST")
    assert not (tmp_path / "new.db").exists()


def test_plaintext_database_from_an_older_release_is_sealed_on_next_commit(tmp_path, plaintext_migration):
    p = tmp_path / "old.db"
    o = sqlite3.connect(p)
    o.execute("CREATE TABLE t(a)")
    o.execute("INSERT INTO t VALUES ('secret-value')")
    o.commit()
    o.close()
    c = ss.connect_sealed(p, "hr:TEST")
    assert c.execute("SELECT a FROM t").fetchone()[0] == "secret-value"
    c.execute("INSERT INTO t VALUES ('two')")
    c.commit()
    assert vault.is_sealed(p.read_bytes()) and b"secret-value" not in p.read_bytes()


def test_a_second_writer_queues_behind_the_first_and_both_updates_survive(tmp_path):
    p = tmp_path / "hr.db"
    a = ss.connect_sealed(p, "hr:TEST")
    a.execute("CREATE TABLE t(a)")
    a.commit()
    b = ss.connect_sealed(p, "hr:TEST")
    b.execute("INSERT INTO t VALUES (1)")
    b.commit()
    a.execute("INSERT INTO t VALUES (2)")               # a re-reads b's commit first, so nothing is lost
    a.commit()
    assert sorted(ss.connect_sealed(p, "hr:TEST").execute("SELECT a FROM t").fetchall()) == [(1,), (2,)]
    assert b.execute("SELECT count(*) FROM t").fetchone()[0] == 2     # and a plain read sees the newer file


def test_newer_schema_is_refused(tmp_path):
    p = tmp_path / "hr.db"
    ss.connect_sealed(p, "hr:TEST", version=3).close()
    with pytest.raises(ss.SchemaTooNew):
        ss.connect_sealed(p, "hr:TEST", version=2)


def test_hr_agent_databases_are_sealed_and_need_the_key(tmp_path, monkeypatch):
    from importlib import import_module
    from velaris.intel.paths import agent_dir
    ats = import_module("departments.hr.RECRUITMENT_ATS.main").RecruitmentTracker()
    ats.add("acme", "Asha Verma", "dev", "c", "asha@example.com", "9999999999")
    raw = (agent_dir("RECRUITMENT_ATS") / "recruitment.db").read_bytes()
    assert vault.is_sealed(raw) and b"asha@example.com" not in raw
    monkeypatch.delenv("VELARIS_VAULT_KEY")
    with pytest.raises(vault.VaultKeyError):
        import_module("departments.hr.RECRUITMENT_ATS.main").RecruitmentTracker()


def test_sealed_stream_roundtrip_and_reordered_or_cut_records_fail(tmp_path):
    import os
    p = tmp_path / "a.bin"
    data = os.urandom(3 * vault.CHUNK + 5)
    assert vault.write_sealed_stream(p, (data[i:i + 700_000] for i in range(0, len(data), 700_000)), "x") == len(data)
    assert vault.read_sealed(p, "x") == data
    with pytest.raises(vault.VaultError):
        list(vault.open_sealed_stream(p, "other"))
    raw = p.read_bytes()
    rec = 16 + vault.CHUNK + 16
    swapped = raw[:4] + raw[4 + rec:4 + 2 * rec] + raw[4:4 + rec] + raw[4 + 2 * rec:]
    p.write_bytes(swapped)
    with pytest.raises(vault.VaultError):
        vault.read_sealed(p, "x")
    p.write_bytes(raw[:4 + rec])                                  # the last record is missing
    with pytest.raises(vault.VaultError):
        vault.read_sealed(p, "x")
