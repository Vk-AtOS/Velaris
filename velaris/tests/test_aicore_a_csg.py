"""CSG family and COHERENCE_SYNC_CORE: state diff/patch, temporal checks, replica drift."""
import pytest

from velaris.agents.COHERENCE_SYNC_CORE.main import COHERENCE_SYNC_COREAgent
from velaris.agents.CSG_STATEALIGN.main import CSG_STATEALIGNAgent
from velaris.agents.CSG_TEMPORAL.main import CSG_TEMPORALAgent


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_statealign_patch_round_trip():
    sa = CSG_STATEALIGNAgent()
    expected = {"price": 100, "tax": {"rate": 18, "code": "GST"}, "active": True}
    actual = {"price": 90, "tax": {"rate": 18}, "legacy": 1}
    r = sa.align(expected, actual)
    assert r["aligned"] is False and r["matching_fields"] == 1
    assert r["patch"] == [{"op": "add", "path": "active", "value": True},
                          {"op": "add", "path": "tax.code", "value": "GST"},
                          {"op": "replace", "path": "price", "value": 100, "was": 90},
                          {"op": "remove", "path": "legacy", "was": 1}]
    fixed = sa.apply(actual, r["patch"])
    assert fixed["state"] == expected and actual["price"] == 90        # input untouched
    assert sa.align(expected, fixed["state"])["aligned"] is True


def test_statealign_bad_input():
    sa = CSG_STATEALIGNAgent()
    assert sa.align([], {})["status"] == "invalid_input" and sa.align({}, {})["aligned"] is True
    assert sa.apply({}, [{"op": "move", "path": "a"}])["status"] == "invalid_input"
    assert sa.apply({}, [{"op": "add", "path": "a"}])["status"] == "invalid_input"
    assert sa.apply("state", [])["status"] == "invalid_input"
    assert sa.apply({"a": 1}, [{"op": "add", "path": "a.b", "value": 2}])["state"] == {"a": {"b": 2}}


def test_temporal_detects_each_kind_of_inconsistency():
    t = CSG_TEMPORALAgent(max_skew=5)
    clean = t.check([{"id": "a", "ts": 1}, {"id": "b", "ts": 2}, {"id": "c", "ts": 3}], max_gap=5, now=10)
    assert clean["consistent"] is True and clean["order"] == ["a", "b", "c"]
    r = t.check([{"id": "a", "ts": 1}, {"id": "c", "ts": 30}, {"id": "b", "ts": 2}, {"id": "a", "ts": 9},
                 {"id": "z", "ts": 100}], max_gap=20, now=40)
    assert r["status"] == "inconsistent" and r["order"] == ["a", "b", "c", "z"]
    assert r["out_of_order"] == [{"id": "b", "ts": 2.0, "behind_by": 28.0}] and r["duplicates"] == ["a"]
    assert r["future"] == [{"id": "z", "ahead_by": 60.0}]
    assert r["gaps"] == [{"after": "b", "before": "c", "gap": 28.0}, {"after": "c", "before": "z", "gap": 70.0}]
    assert t.check([{"id": "a", "ts": 44}], now=40)["consistent"] is True     # within allowed skew
    assert t.check([], now=1)["consistent"] is True


def test_temporal_bad_input():
    t = CSG_TEMPORALAgent()
    assert t.check("events")["status"] == "invalid_input"
    assert t.check([{"id": "a"}])["consistent"] is False
    assert t.check([{"id": "a", "ts": "noon"}])["status"] == "invalid_input"
    assert t.check([], max_gap=0)["status"] == "invalid_input"


def test_sync_finds_drift_and_patch_restores_it():
    sync = COHERENCE_SYNC_COREAgent()
    good = {"price_list": "v7", "tax": {"rate": 18}}
    sync.report("hq", good, ts=100, now=200)
    sync.report("pune", good, ts=101, now=200)
    assert sync.check()["coherent"] is True
    sync.report("dubai", {"price_list": "v6", "tax": {"rate": 5}}, ts=40, now=200)
    r = COHERENCE_SYNC_COREAgent().check(max_lag=30)                    # new instance: persisted
    assert r["status"] == "drift" and r["divergent"] == ["dubai"] and r["lagging"] == ["dubai"]
    assert r["in_sync"] == ["hq", "pune"]
    repaired = CSG_STATEALIGNAgent().apply({"price_list": "v6", "tax": {"rate": 5}}, r["patches"]["dubai"])["state"]
    assert repaired == good
    sync.report("dubai", repaired, ts=150, now=200)
    assert sync.check(max_lag=60)["status"] == "ok"


def test_sync_split_stale_skew_and_bad_input():
    sync = COHERENCE_SYNC_COREAgent()
    assert sync.check()["status"] == "no_data"
    sync.report("a", {"v": 1}, ts=10, now=20)
    sync.report("b", {"v": 2}, ts=10, now=20)
    split = sync.check()
    assert split["status"] == "split" and split["coherent"] is False and split["patches"] == {}
    assert sync.report("a", {"v": 9}, ts=5, now=20)["status"] == "stale"
    assert sync.report("a", {"v": 9}, ts=500, now=20)["status"] == "clock_skew"
    assert sync.report("", {"v": 1})["status"] == "invalid_input"
    assert sync.report("c", "state")["status"] == "invalid_input"
    assert sync.forget("b")["status"] == "ok" and sync.forget("b")["status"] == "not_found"
    assert sync.check()["coherent"] is True
