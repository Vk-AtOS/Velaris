"""KAN-113: every sqlite store carries a schema version with a migration hook; old in-tree databases are adopted once."""
import importlib
import sqlite3
from pathlib import Path

import pytest

from velaris.core import sqlite_util
from velaris.intel import paths

ROOT = Path(__file__).resolve().parents[2]


def test_new_database_is_stamped_and_runs_migrations_atomically(tmp_path):
    db = tmp_path / "x.db"
    seen = []
    c = sqlite_util.connect(db, 3, {2: lambda conn: seen.append(2), 3: lambda conn: seen.append(3)})
    assert c.execute("PRAGMA user_version").fetchone()[0] == 3 and seen == [2, 3]
    c.close()

    def boom(conn):
        conn.execute("CREATE TABLE half(a)")
        raise ValueError("migration bug")
    with pytest.raises(ValueError):
        sqlite_util.connect(db, 4, {4: boom})
    c = sqlite_util.connect(db, 3)                       # still version 3, and the half-made table is gone
    assert c.execute("PRAGMA user_version").fetchone()[0] == 3
    assert c.execute("SELECT name FROM sqlite_master WHERE name='half'").fetchone() is None


def test_a_database_from_a_newer_release_is_refused(tmp_path):
    db = tmp_path / "x.db"
    sqlite_util.connect(db, 5).close()
    with pytest.raises(sqlite_util.SchemaTooNew):
        sqlite_util.connect(db, 4)


def test_unversioned_old_database_becomes_version_1_with_its_data(tmp_path):
    db = tmp_path / "old.db"
    old = sqlite3.connect(db)
    old.execute("CREATE TABLE t(a)")
    old.execute("INSERT INTO t VALUES (7)")
    old.commit()
    old.close()
    c = sqlite_util.connect(db)
    assert c.execute("PRAGMA user_version").fetchone()[0] == 1 and c.execute("SELECT a FROM t").fetchone()[0] == 7


def test_agent_adopts_the_database_an_older_release_left_in_the_source_tree(monkeypatch):
    legacy = ROOT / "departments" / "operations" / "SLA_MONITOR" / "sla_data.db"
    assert not legacy.exists()
    try:
        c = sqlite3.connect(legacy)
        c.execute("CREATE TABLE marker(v)")
        c.execute("INSERT INTO marker VALUES ('kept')")
        c.commit()
        c.close()
        agent = importlib.import_module("velaris.agents.SLA_MONITOR.main").SLAMonitorAgent()
        assert agent
        new = sqlite3.connect(paths.agent_file("SLA_MONITOR", "sla_data.db"))
        assert new.execute("SELECT v FROM marker").fetchone()[0] == "kept"
        assert new.execute("PRAGMA user_version").fetchone()[0] == 1
        assert legacy.exists()                            # the original is never moved or deleted
    finally:
        legacy.unlink(missing_ok=True)


def test_adoption_skips_an_existing_file_a_non_database_and_can_be_disabled(tmp_path, monkeypatch):
    junk = tmp_path / "cwd"
    junk.mkdir()
    (junk / "reviews.db").write_text("not a database")
    monkeypatch.chdir(junk)
    dest = Path(paths.agent_dir("PERFORMANCE_REVIEW_ENGINE")) / "reviews.db"
    assert paths.adopt_legacy("PERFORMANCE_REVIEW_ENGINE", dest) is False and not dest.exists()
    monkeypatch.setenv("VELARIS_ADOPT_LEGACY", "0")
    good = sqlite3.connect(junk / "reviews.db")      # overwrite junk with a real database
    good.close()
    assert paths.adopt_legacy("PERFORMANCE_REVIEW_ENGINE", dest) is False
