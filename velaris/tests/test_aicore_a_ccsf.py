"""CCSF family: N-source fusion, conflict resolution strategies, persistent agreed state."""
import pytest

from velaris.agents.CCSF_CORE.main import CCSF_COREAgent
from velaris.agents.CCSF_FUSION.main import CCSF_FUSIONAgent
from velaris.agents.CCSF_RESOLVER.main import CCSF_RESOLVERAgent

SOURCES = [{"source": "crm", "ts": 10, "data": {"name": "Acme", "city": "Pune", "credit": 5}},
           {"source": "erp", "ts": 30, "data": {"name": "Acme", "city": "Mumbai", "credit": 9}},
           {"source": "portal", "ts": 20, "data": {"city": "Mumbai", "credit": 7, "phone": "1"}}]


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_fusion_of_three_sources():
    r = CCSF_FUSIONAgent().fuse(SOURCES)
    assert r["status"] == "conflict" and r["merged"] == {"name": "Acme", "phone": "1"}
    assert [c["field"] for c in r["conflicts"]] == ["city", "credit"] and r["agreement"] == 0.5
    assert r["provenance"] == {"name": ["crm", "erp"], "phone": ["portal"]}
    agree = CCSF_FUSIONAgent().fuse(SOURCES[:1])
    assert agree["status"] == "ok" and agree["agreement"] == 1.0


def test_fusion_bad_input():
    f = CCSF_FUSIONAgent().fuse
    assert f([])["status"] == "invalid_input" and f("x")["status"] == "invalid_input"
    assert f([{"source": "a", "data": []}])["status"] == "invalid_input"
    assert f([{"source": "a", "data": {}, "ts": "yesterday"}])["status"] == "invalid_input"
    assert f([SOURCES[0], SOURCES[0]])["status"] == "invalid_input"


def test_resolver_strategies():
    conflicts = CCSF_FUSIONAgent().fuse(SOURCES)["conflicts"]
    res = CCSF_RESOLVERAgent().resolve
    r = res(conflicts, {"city": "majority", "credit": "latest"})
    assert r["status"] == "ok" and r["resolved"]["city"]["value"] == "Mumbai"
    assert r["resolved"]["credit"] == {"value": 9, "source": "erp", "why": "newest timestamp (30)"}
    assert res(conflicts, {"credit": "min"}, default="majority")["resolved"]["credit"]["source"] == "crm"
    pr = res(conflicts, default={"priority": ["sap", "portal", "erp"]})
    assert {f: v["source"] for f, v in pr["resolved"].items()} == {"city": "portal", "credit": "portal"}


def test_resolver_leaves_undecidable_fields_for_a_person():
    conflicts = CCSF_FUSIONAgent().fuse(SOURCES)["conflicts"]
    res = CCSF_RESOLVERAgent().resolve
    manual = res(conflicts)
    assert manual["status"] == "unresolved" and manual["resolved"] == {} and len(manual["unresolved"]) == 2
    r = res(conflicts, {"credit": "majority", "city": "max"})
    assert {u["field"]: u["reason"] for u in r["unresolved"]} == {
        "credit": "no value is reported by more than half the sources", "city": "a value is not numeric"}
    tie = [{"field": "x", "values": [{"source": "a", "value": 1, "ts": 5}, {"source": "b", "value": 2, "ts": 5}]}]
    assert res(tie, default="latest")["unresolved"][0]["reason"] == "the two newest values have the same timestamp"
    no_ts = [{"field": "x", "values": [{"source": "a", "value": 1}, {"source": "b", "value": 2, "ts": 5}]}]
    assert res(no_ts, default="latest")["status"] == "unresolved"
    assert res(tie, default={"priority": ["z"]})["unresolved"][0]["reason"] == "no listed source reported this field"


def test_resolver_bad_input():
    res = CCSF_RESOLVERAgent().resolve
    assert res([], default="coin_flip")["status"] == "invalid_input"
    assert res("x")["status"] == "invalid_input"
    assert res([{"field": "x", "values": [{"source": "a", "value": 1}]}])["status"] == "invalid_input"
    assert res([])["status"] == "ok"


def test_core_keeps_agreed_state_across_restart():
    core = CCSF_COREAgent({"city": "latest"})
    for s in SOURCES:
        assert core.ingest("cust-1", s["source"], s["data"], s["ts"])["status"] == "ok"
    v = CCSF_COREAgent({"city": "latest"}).view("cust-1")           # new instance
    assert v["status"] == "unresolved" and v["state"] == {"name": "Acme", "phone": "1", "city": "Mumbai"}
    assert v["provenance"]["city"] == ["erp"] and [u["field"] for u in v["unresolved"]] == ["credit"]
    assert core.ingest("cust-1", "crm", {"city": "Delhi"}, ts=5)["status"] == "stale"
    core.ingest("cust-1", "crm", {"name": "Acme", "city": "Delhi", "credit": 9}, ts=40)
    core.ingest("cust-1", "portal", {"credit": 9}, ts=41)
    v2 = core.view("cust-1")
    assert v2["status"] == "ok" and v2["state"] == {"name": "Acme", "city": "Delhi", "credit": 9}


def test_core_bad_input():
    core = CCSF_COREAgent()
    assert core.ingest("", "crm", {})["status"] == "invalid_input"
    assert core.ingest("c", "crm", "data")["status"] == "invalid_input"
    assert core.ingest("c", "crm", {}, ts="now")["status"] == "invalid_input"
    assert core.view("nobody")["status"] == "not_found" and core.view(None)["status"] == "not_found"
    core.ingest("c", "a", {"x": 1}, 1)
    core.ingest("c", "b", {"x": 2}, 2)
    assert CCSF_COREAgent(default_strategy="guess").view("c")["status"] == "not_configured"
