"""KAN-68: legacy rows without an organisation get VELARIS_ORG; dry run first, idempotent, refuses without VELARIS_ORG."""
import sqlite3

import pytest

from velaris.agentkit.state import JsonState
from velaris.core import backfill_org as b
from velaris.intel.paths import agent_file


def _leave_db(rows):
    c = sqlite3.connect(agent_file("LEAVE_MANAGEMENT", "leaves.db"))
    c.execute("CREATE TABLE leave_requests(id INTEGER PRIMARY KEY, employee_id TEXT, org TEXT)")
    c.executemany("INSERT INTO leave_requests(employee_id, org) VALUES (?,?)", rows)
    c.commit()
    c.close()


def _orgs():
    c = sqlite3.connect(agent_file("LEAVE_MANAGEMENT", "leaves.db"))
    return [r[0] for r in c.execute("SELECT org FROM leave_requests ORDER BY id")]


@pytest.fixture
def world(monkeypatch):
    monkeypatch.setenv("VELARIS_ORG", "acme")
    _leave_db([("e1", None), ("e2", ""), ("e3", "acme"), ("e4", "globex")])
    JsonState("ITSM_ENGINE", "tickets.json").save({"tickets": {"T1": {"id": "T1"}, "T2": {"id": "T2", "org": "globex"}}})


def test_dry_run_reports_and_changes_nothing(world):
    r = b.backfill()
    assert r["dry_run"] and r["total_found"] == 3 and r["total_updated"] == 0
    assert _orgs() == [None, "", "acme", "globex"]
    assert "org" not in JsonState("ITSM_ENGINE", "tickets.json").load()["tickets"]["T1"]


def test_apply_fills_only_unstamped_rows_and_rerun_changes_nothing(world):
    r = b.backfill(apply=True)
    assert r["total_updated"] == 3
    assert _orgs() == ["acme", "acme", "acme", "globex"]           # another organisation's row is left alone
    t = JsonState("ITSM_ENGINE", "tickets.json").load()["tickets"]
    assert t["T1"]["org"] == "acme" and t["T2"]["org"] == "globex"
    again = b.backfill(apply=True)
    assert again["total_found"] == 0 and again["total_updated"] == 0


def test_refuses_without_an_organisation(monkeypatch):
    monkeypatch.delenv("VELARIS_ORG", raising=False)
    with pytest.raises(b.BackfillError):
        b.backfill(apply=True)
    assert b.main(["--apply"]) == 2


def test_missing_stores_are_skipped(monkeypatch):
    monkeypatch.setenv("VELARIS_ORG", "acme")
    assert b.backfill(apply=True)["stores"] == {}
