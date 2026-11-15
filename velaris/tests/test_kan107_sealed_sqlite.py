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


def test_plaintext_database_from_an_older_release_is_sealed_on_next_commit(tmp_path):
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


def test_a_second_process_writing_in_between_is_a_conflict_not_a_lost_update(tmp_path):
    p = tmp_path / "hr.db"
    a = ss.connect_sealed(p, "hr:TEST")
    a.execute("CREATE TABLE t(a)")
    a.commit()
    b = ss.connect_sealed(p, "hr:TEST")
    b.execute("INSERT INTO t VALUES (1)")
    b.commit()
    a.execute("INSERT INTO t VALUES (2)")
    with pytest.raises(ss.SealedConflict):
        a.commit()
    assert ss.connect_sealed(p, "hr:TEST").execute("SELECT a FROM t").fetchall() == [(1,)]


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
