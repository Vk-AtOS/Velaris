"""Round 3 (KAN-93, KAN-94-adjacent aicore remainders): patch history honesty, evolution reads metrics, search stores, CLBPP."""
import pytest

from velaris.agents.ADVANCED_SEARCH_ENGINE.main import AdvancedSearchEngine
from velaris.agents.AGENT_EVOLUTION.main import EvolutionEngine
from velaris.agents.AUTONOMOUS_PATCH_ENGINE.main import AutonomousPatchEngine
from velaris.agents.AUTONOMOUS_RESEARCH_ENGINE.main import AutonomousResearchEngine
from velaris.agents.CLBPP_DISTRIBUTOR.main import CLBPP_DISTRIBUTORAgent
from velaris.core.access import Caller, acting_as

ASHA = Caller("asha", "acme")


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_patch_engine_needs_a_caller_records_who_and_does_not_claim_it_applied_anything():
    e = AutonomousPatchEngine()
    patch = {"target": "cfg", "changes": {"a": 2}}
    with pytest.raises(PermissionError):
        e.apply_patch({"a": 1}, patch)
    assert e.get_history() == []
    with acting_as(ASHA):
        out = e.apply_patch({"a": 1}, patch)
    assert out == {"a": 2}
    h = AutonomousPatchEngine().get_history()                       # a second worker reads the same file
    assert len(h) == 1 and h[0]["status"] == "COMPUTED" and h[0]["by"] == "asha" and h[0]["before"] != h[0]["after"]
    for bad in ({"target": "", "changes": {}}, {"target": "t", "changes": {1: 2}}, {"target": "t", "changes": {"x": {1, 2}}},
                {"changes": {}}, "nope"):
        assert e.validate_patch(bad) is False
    with pytest.raises(ValueError):
        e.simulate_patch({}, {"target": "t"})                       # used to be a KeyError


def test_evolution_proposes_only_when_a_cost_metric_gets_worse():
    e = EvolutionEngine()
    for _ in range(8):
        e.record("steady", {"loss": 1.0})
    for i in range(8):
        e.record("worse", {"loss": float(i)})
    for i in range(8):
        e.record("better", {"loss": float(8 - i)})
    assert [e.propose(a)["proposal"] for a in ("steady", "worse", "better", "unknown")] == ["none", "tune-params", "none", "none"]
    assert e.record("x", {"loss": float("nan")})["ok"] is False and e.record("x", "m")["ok"] is False
    assert e.record("", {"loss": 1})["ok"] is False
    for i in range(300):
        e.record("long", {"loss": 1})
    assert len(e.history["long"]) == 200
    assert EvolutionEngine("bad").health_check()["status"] == "ok"


@pytest.mark.parametrize("make, add, find", [
    (AdvancedSearchEngine, ("register_dataset", "add_record"), "search"),
    (AutonomousResearchEngine, ("register_source", "add_document"), "query")])
def test_the_two_search_agents_share_one_bounded_store(make, add, find):
    e = make()
    reg, put = getattr(e, add[0]), getattr(e, add[1])
    assert reg("Notes") and not reg("notes") and not reg(None) and not reg("  ")
    rec = {"t": "Hello world", "u": "hello"}
    assert put("NOTES", rec) and not put("missing", rec) and not put("notes", "not a dict")
    rec["t"] = "changed after"                                      # stored copy is unaffected
    search = getattr(e, find)
    hits = search("hello")
    assert len(hits) == 1 and hits[0]["score"] == 2
    hits[0].get("record", hits[0].get("document"))["t"] = "mutated"  # nor can a hit edit the store
    assert search("hello world")[0]["score"] == 1
    assert search(None) == [] and search("") == [] and search("  ") == [] and search(5) == []


def test_clbpp_says_whether_everything_was_placed_and_why_not():
    d = CLBPP_DISTRIBUTORAgent()
    r = d.distribute([{"id": "a", "effort": 3}, {"id": "huge", "effort": 50}, {"id": "later", "effort": 8}],
                     [{"name": "w", "capacity": 10, "load": 5}])
    assert r["complete"] is False and r["assignments"] == {"a": "w"}
    why = {u["id"]: u["reason"] for u in r["unassigned"]}
    assert why["huge"].startswith("too big") and "spare capacity" in why["later"]
    assert d.distribute([{"id": "a", "effort": 1}], [{"name": "w", "capacity": 2}])["complete"] is True
    assert d.distribute([], [{"name": "w", "capacity": 2, "skills": [1]}])["status"] == "invalid_input"
