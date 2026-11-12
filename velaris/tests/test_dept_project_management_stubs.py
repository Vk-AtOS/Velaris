"""Project-management agents that used to be stubs."""
import pytest

from velaris.agents.ACTION_SANDBOX.main import ACTION_SANDBOXAgent
from velaris.agents.FEASIBILITY_ENGINE.main import FEASIBILITY_ENGINEAgent
from velaris.agents.INITIATIVE_ENGINE.main import InitiativeEngine


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_sandbox_simulates_on_a_copy():
    state = {"headcount": 20, "tags": ["a"]}
    box = ACTION_SANDBOXAgent()
    r = box.sandbox_execute({"op": "increment", "key": "headcount", "by": 3}, state)
    assert r["result"] == "simulated" and r["changes"] == [{"key": "headcount", "before": 20, "after": 23}]
    assert state == {"headcount": 20, "tags": ["a"]}                      # caller's state untouched
    appended = box.sandbox_execute({"op": "append", "key": "tags", "value": "b"}, state)
    assert appended["state_after"]["tags"] == ["a", "b"] and state["tags"] == ["a"]
    assert box.sandbox_execute({"op": "set", "key": "headcount", "value": 20}, state)["changes"] == []
    assert box.sandbox_execute({"op": "delete", "key": "tags"}, state)["changes"][0]["after"] == "<absent>"


def test_sandbox_unknown_and_bad_actions():
    box = ACTION_SANDBOXAgent()
    r = box.sandbox_execute({"do": "thing"})
    assert (r["status"], r["result"], r["changes"]) == ("unsupported", "simulated", [])
    assert box.sandbox_execute({"op": "delete", "key": "x"}, {})["status"] == "failed"
    assert box.sandbox_execute({"op": "increment", "key": "x", "by": "1"})["status"] == "failed"
    assert box.sandbox_execute({"op": "set", "key": ""})["status"] == "failed"
    assert box.sandbox_execute("rm -rf /")["status"] == "failed"


def test_feasibility_scored_checklist_with_computed_criteria():
    r = FEASIBILITY_ENGINEAgent().assess({
        "name": "Clinic portal",
        "budget": {"required": 1050000, "available": 1000000},                 # within 10% over -> 2
        "schedule": {"effort_person_days": 180, "people": 4, "working_days": 50},   # load 90% -> 3
        "criteria": {"technical": {"rating": 4, "evidence": "Same stack as the last two portals"},
                     "resources": {"rating": 3, "evidence": "Two seniors free from December"},
                     "compliance": {"rating": 4, "evidence": "Legal reviewed data handling on 2026-11-01"}}})
    # 25 + 25 x 2/4 + 20 x 3/4 + 20 x 3/4 + 10 = 77.5
    assert (r["score"], r["verdict"]) == (77.5, "feasible")
    rows = {c["criterion"]: c for c in r["criteria"]}
    assert rows["financial"]["evidence"].startswith("computed: required 1050000.00")
    assert rows["schedule"]["rating"] == 3 and sum(r["weights"].values()) == 100


def test_feasibility_evidence_gaps_and_blockers():
    eng = FEASIBILITY_ENGINEAgent()
    gaps = eng.assess({"name": "X", "criteria": {"technical": {"rating": 4, "evidence": ""}}})
    assert gaps["verdict"] == "insufficient_evidence" and "technical" in gaps["missing_evidence"]
    full = {k: {"rating": 4, "evidence": "ok"} for k in ("technical", "resources", "compliance", "schedule")}
    blocked = eng.assess({"name": "X", "budget": {"required": 200, "available": 100}, "criteria": full})
    assert (blocked["verdict"], blocked["blocking_criteria"], blocked["score"]) == ("not_feasible", ["financial"], 75.0)


def test_feasibility_bad_input():
    eng = FEASIBILITY_ENGINEAgent()
    assert eng.assess({"criteria": {}})["status"] == "failed"
    assert eng.assess({"name": "X", "criteria": {"vibes": {"rating": 4}}})["status"] == "failed"
    assert eng.assess({"name": "X", "criteria": {"technical": {"rating": 9, "evidence": "x"}}})["status"] == "failed"
    assert eng.assess({"name": "X", "budget": {"required": -1, "available": 1}})["status"] == "failed"
    assert eng.assess({"name": "X", "budget": {"required": 1, "available": 1},
                       "criteria": {"financial": {"rating": 4, "evidence": "x"}}})["status"] == "failed"


def test_initiatives_ranked_by_rice_and_kept():
    r = InitiativeEngine().propose({"initiatives": [
        {"name": "WhatsApp invoices", "reach": 200, "impact": 2, "confidence": 0.8, "effort": 4},   # 80
        {"name": "Tamil UI", "reach": 500, "impact": 1, "confidence": 0.5, "effort": 2},           # 125
        {"name": "AI chatbot", "reach": 1000, "impact": 3, "confidence": 0.2, "effort": 10}]})     # 60
    assert [(x["name"], x["rice"], x["rank"]) for x in r["ranked"]] == [
        ("Tamil UI", 125.0, 1), ("WhatsApp invoices", 80.0, 2), ("AI chatbot", 60.0, 3)]
    assert r["idea"] == "Tamil UI"
    assert [x["name"] for x in InitiativeEngine().register()["ranked"]][0] == "Tamil UI"


def test_initiatives_empty_and_bad_input():
    eng = InitiativeEngine()
    assert eng.propose({})["status"] == "needs_data" and eng.register()["status"] == "needs_data"
    assert eng.propose({"initiatives": [{"name": "x", "reach": 1, "impact": 1, "confidence": 2, "effort": 1}]})["status"] == "failed"
    assert eng.propose({"initiatives": [{"name": "x", "reach": 1, "impact": 1, "confidence": 1, "effort": 0}]})["status"] == "failed"
    assert eng.propose("ideas")["status"] == "failed"
