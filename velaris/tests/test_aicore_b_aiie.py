"""Intent -> graph check -> nested plan -> task queue: INTENT_SYNTHESIZER, HYPER_REASONER,
RECURSIVE_GOAL_PLANNER, SELF_DIRECTED_TASKER (with the neighbouring DECISION_GRAPH_ENGINE)."""
import json

import pytest

from velaris.agents.DECISION_GRAPH_ENGINE.main import DecisionGraphEngine
from velaris.agents.HYPER_REASONER.main import HyperReasoner
from velaris.agents.INTENT_SYNTHESIZER.main import IntentSynthesizer
from velaris.agents.RECURSIVE_GOAL_PLANNER.main import RecursiveGoalPlanner
from velaris.agents.SELF_DIRECTED_TASKER.main import SelfDirectedTasker
from velaris.intel.llm import FakeLLM


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    for key in ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "AWS_BEARER_TOKEN_BEDROCK"):
        monkeypatch.delenv(key, raising=False)
    return tmp_path


# ---- INTENT_SYNTHESIZER ------------------------------------------------------

def test_intent_extracts_action_object_and_constraints():
    r = IntentSynthesizer().synthesize({"idea": "Please onboard the new vendor Acme by 2026-12-15 within Rs. 2 lakh"})
    i = r["intent"]
    assert r["status"] == "ok" and i["complete"] is True
    assert i["action"] == "onboard" and i["object"].startswith("new vendor acme")
    assert i["constraints"] == {"budget": {"value": 200000.0, "currency": "INR"}, "deadline": "2026-12-15",
                                "references": []}
    assert "proposed_by_model" not in i


def test_intent_vague_idea_is_incomplete_not_guessed():
    r = IntentSynthesizer().synthesize("growth")
    assert r["status"] == "incomplete" and r["intent"]["missing"] == ["action", "object"]
    assert IntentSynthesizer().synthesize({"context": {"x": 1}})["status"] == "invalid_input"
    assert IntentSynthesizer().synthesize("")["intent"] is None


def test_intent_model_only_adds_labelled_proposals():
    llm = FakeLLM({"Restate the goal": json.dumps({"goal": "Bring Acme on as a supplier",
                                                   "success_criteria": ["contract signed", "vendor code issued"]})})
    r = IntentSynthesizer().synthesize("Onboard vendor Acme for Rs. 50,000", llm=llm)
    assert r["intent"]["proposed_by_model"]["success_criteria"] == ["contract signed", "vendor code issued"]
    assert r["intent"]["constraints"]["budget"]["value"] == 50000.0          # from the text, not the model
    assert "Onboard vendor Acme" in llm.calls[0]["prompt"] and "BEGIN DATA-" in llm.calls[0]["prompt"]
    bad = IntentSynthesizer().synthesize("Onboard vendor Acme", llm=FakeLLM({"Restate": '{"goal": 5}'}))
    assert bad["model"]["status"] == "rejected" and "proposed_by_model" not in bad["intent"]
    broken = IntentSynthesizer().synthesize("Onboard vendor Acme", llm=FakeLLM({"Restate": "no json here"}))
    assert broken["model"]["status"] == "model_error" and broken["status"] == "ok"


# ---- HYPER_REASONER ----------------------------------------------------------

def test_reasoner_validates_a_graph_from_the_decision_graph_engine():
    dge = DecisionGraphEngine().graph({"steps": [{"id": "quote", "depends_on": []},
                                                 {"id": "approve", "depends_on": ["quote"]},
                                                 {"id": "order", "depends_on": ["approve"]}]})
    r = HyperReasoner().reason(dge)
    assert r["validated"] is True and r["order"] == ["quote", "approve", "order"]
    assert r["steps"][2] == {"id": "order", "title": "order", "depends_on": ["approve"]}


@pytest.mark.parametrize("graph, issue", [
    ({"nodes": ["a", "b"], "edges": [["a", "b"], ["b", "a"]]}, "cycle"),
    ({"nodes": ["a", "b", "c"], "edges": [["a", "b"]], "start": "a"}, "cannot be reached"),
    ({"nodes": ["a"], "edges": [["a", "zz"]]}, "unknown node"),
    ({"nodes": ["a", "a"]}, "duplicate"),
    ({"nodes": []}, "no nodes"),
    ({"nodes": ["a"], "start": "q"}, "start node"),
    ({"nodes": ["a"], "edges": ["a->b"]}, "unreadable edge"),
])
def test_reasoner_reports_structural_problems(graph, issue):
    r = HyperReasoner().reason(graph)
    assert r["validated"] is False and any(issue in i for i in r["issues"]) and r["steps"] == []


def test_reasoner_bad_input_and_plain_sequences():
    assert HyperReasoner().reason("graph")["status"] == "invalid_input"
    assert HyperReasoner().reason({"edges": []})["status"] == "invalid_input"
    seq = HyperReasoner().reason({"steps": ["draft", "review", "send"]})
    assert seq["validated"] is True and seq["order"] == ["draft", "review", "send"]


# ---- RECURSIVE_GOAL_PLANNER --------------------------------------------------

NESTED = {"goal": "Launch the vendor portal", "subgoals": [
    {"id": "build", "title": "Build", "subgoals": [{"id": "api", "title": "API"},
                                                    {"id": "ui", "title": "UI", "depends_on": ["api"]}]},
    {"id": "test", "title": "Test", "depends_on": ["build"]},
    {"id": "launch", "title": "Launch", "depends_on": ["test"], "subgoals": ["Announce", "Train staff"]},
]}


def test_planner_flattens_nested_goals_with_group_dependencies():
    r = RecursiveGoalPlanner().recurse(NESTED)
    plan = r["expanded"]
    assert r["status"] == "ok" and plan["goal"] == "Launch the vendor portal"
    deps = {t["id"]: t["depends_on"] for t in plan["tasks"]}
    assert deps == {"api": [], "ui": ["api"], "test": ["api", "ui"], "launch.1": ["test"], "launch.2": ["test"]}
    assert plan["order"] == ["api", "ui", "test", "launch.1", "launch.2"]
    assert plan["levels"][-1] == ["launch.1", "launch.2"]


def test_planner_takes_the_reasoner_output_and_refuses_an_invalid_graph():
    checked = HyperReasoner().reason({"nodes": ["a", "b", "c"], "edges": [["a", "b"], ["a", "c"]]})
    r = RecursiveGoalPlanner().recurse(checked)
    assert r["status"] == "ok" and r["expanded"]["levels"] == [["a"], ["b", "c"]]
    bad = RecursiveGoalPlanner().recurse(HyperReasoner().reason({"nodes": ["a", "b"], "edges": [["a", "b"], ["b", "a"]]}))
    assert bad["status"] == "invalid" and "cycle" in bad["reason"]


@pytest.mark.parametrize("plan, fragment", [
    ({"subgoals": [{"id": "a", "title": "A", "depends_on": ["b"]}, {"id": "b", "title": "B", "depends_on": ["a"]}]},
     "cycle"),
    ({"subgoals": [{"id": "a", "title": "A", "depends_on": ["ghost"]}]}, "unknown dependency"),
    ({"subgoals": [{"id": "a", "title": "A"}, {"id": "a", "title": "B"}]}, "duplicate"),
    ({"subgoals": [{"id": "a"}]}, "title"),
    ({"subgoals": "do things"}, "must be a list"),
])
def test_planner_rejects_broken_plans(plan, fragment):
    r = RecursiveGoalPlanner().recurse(plan)
    assert r["status"] == "invalid" and fragment in r["reason"] and r["expanded"] is None


def test_planner_single_goal_and_bad_input():
    single = RecursiveGoalPlanner().recurse({"goal": "File GST return"})
    assert single["expanded"]["tasks"][0]["title"] == "File GST return"
    assert RecursiveGoalPlanner().recurse({})["status"] == "invalid_input"
    assert RecursiveGoalPlanner().recurse(None)["status"] == "invalid_input"
    deep = {"subgoals": [{"title": "x"}]}
    for _ in range(8):
        deep = {"subgoals": [{"title": "level", "subgoals": deep["subgoals"]}]}
    assert "deeper" in RecursiveGoalPlanner().recurse(deep)["reason"]


def test_planner_decompose_validates_the_model_plan():
    planner = RecursiveGoalPlanner()
    assert planner.decompose("Open a Chennai office")["status"] == "not_configured"
    good = FakeLLM({"Break the goal": json.dumps({"subgoals": [
        {"id": "a", "title": "Find premises"}, {"id": "b", "title": "Sign lease", "depends_on": ["a"]}]})})
    r = planner.decompose("Open a Chennai office", llm=good)
    assert r["status"] == "ok" and r["proposed_by_model"] and r["expanded"]["order"] == ["a", "b"]
    looping = FakeLLM({"Break the goal": json.dumps({"subgoals": [
        {"id": "a", "title": "A", "depends_on": ["b"]}, {"id": "b", "title": "B", "depends_on": ["a"]}]})})
    assert planner.decompose("Open a Chennai office", llm=looping)["status"] == "rejected"
    assert planner.decompose("Open an office", llm=FakeLLM({"Break": "[]"}))["status"] == "rejected"
    assert planner.decompose("", llm=good)["status"] == "invalid_input"


# ---- SELF_DIRECTED_TASKER ----------------------------------------------------

def test_tasker_releases_tasks_as_dependencies_finish_across_restarts():
    plan = RecursiveGoalPlanner().recurse(NESTED)
    prepared = SelfDirectedTasker().prepare(plan)
    assert prepared["task_ready"] is True and prepared["ready"] == ["api"] and prepared["blocked"]["test"] == ["api", "ui"]
    started = SelfDirectedTasker().start(plan)
    qid = started["plan_id"]
    t = SelfDirectedTasker()
    assert t.complete(qid, "test")["status"] == "blocked"
    assert t.complete(qid, "api")["released"] == ["ui"]
    assert SelfDirectedTasker().complete(qid, "ui")["released"] == ["test"]           # state survives a restart
    assert t.complete(qid, "ui")["status"] == "already_done"
    t.complete(qid, "test")
    assert [x["id"] for x in t.next_tasks(qid)["ready"]] == ["launch.1", "launch.2"]
    t.complete(qid, "launch.1")
    last = t.complete(qid, "launch.2")
    assert last["finished"] is True and t.next_tasks(qid)["finished"] is True


def test_tasker_bad_input():
    t = SelfDirectedTasker()
    assert t.prepare({"expanded": {"x": 1}})["status"] == "invalid_input"
    assert t.prepare({"tasks": [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]})["status"] \
        == "deadlocked"
    assert t.prepare({"tasks": [{"id": "a", "depends_on": ["ghost"]}]})["status"] == "invalid_input"
    assert t.start({"tasks": []})["plan_id"] is None
    assert t.next_tasks("queue-missing")["status"] == "not_found"
    assert t.complete("queue-missing", "a")["status"] == "not_found"
    qid = t.start({"tasks": [{"id": "a"}]})["plan_id"]
    assert t.complete(qid, "zz")["status"] == "invalid_input"
