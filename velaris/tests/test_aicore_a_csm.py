"""CSM family: goal standing, link register, generated policies, goal register."""
import pytest

from velaris.agents.CSM_CORE.main import CSMCoreAgent
from velaris.agents.CSM_LINKER.main import CSMLinkerAgent
from velaris.agents.CSM_POLICY.main import CSMPolicyAgent
from velaris.agents.CSM_REASONER.main import CSMReasonerAgent

SPEC = {"name": "discount", "required": ["approver"], "limits": {"percent": {"min": 0, "max": 15}},
        "allowed": {"region": ["IN", "AE"]}}


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_reasoner_decision_table():
    q = CSMReasonerAgent().quick_strategy

    def situation(current, elapsed):
        r = q({"current": current, "target": 100, "elapsed": elapsed, "total": 10})
        return r["situation"], r["strategy"]
    assert situation(100, 4) == ("achieved", "sustain")
    assert situation(50, 5) == ("on_track", "hold_course")
    assert situation(45, 5) == ("at_risk", "accelerate")          # pace 0.9
    assert situation(20, 5) == ("off_track", "escalate")          # pace 0.4
    assert situation(90, 10) == ("missed", "replan")
    assert situation(0, 0) == ("on_track", "hold_course")         # nothing to judge yet
    r = q({"current": 20, "target": 100, "elapsed": 5, "total": 10})
    assert (r["progress"], r["pace"], r["current_rate"], r["required_rate"]) == (0.2, 0.4, 4.0, 16.0)
    down = q({"start": 50, "current": 30, "target": 10, "elapsed": 5, "total": 10})   # a metric to bring down
    assert down["situation"] == "on_track" and down["required_rate"] == -4.0


def test_reasoner_bad_input():
    q = CSMReasonerAgent().quick_strategy
    for bad in ("X", None, {}, {"current": 1, "target": 1, "elapsed": 1, "total": 1, "start": 1},
                {"current": 1, "target": 5, "elapsed": 1, "total": 0}, {"current": "1", "target": 5, "elapsed": 1, "total": 2}):
        r = q(bad)
        assert r["status"] == "invalid_input" and r["strategy"] is None


def test_linker_registers_links_once_and_finds_paths():
    linker = CSMLinkerAgent()
    assert linker.link("goal:q3", "team:sales", "owned_by")["created"] is True
    assert linker.link("team:sales", "goal:q3", "owned_by")["created"] is False     # same link, either direction
    linker.link("team:sales", "person:asha", "led_by")
    linker.link("goal:q4", "team:ops", "owned_by")
    again = CSMLinkerAgent()                                                         # persisted
    assert again.neighbours("team:sales") == [{"item": "goal:q3", "relation": "owned_by"},
                                               {"item": "person:asha", "relation": "led_by"}]
    assert again.neighbours("team:sales", "led_by") == [{"item": "person:asha", "relation": "led_by"}]
    assert again.path("goal:q3", "person:asha")["path"] == ["goal:q3", "team:sales", "person:asha"]
    assert again.path("goal:q3", "goal:q4")["status"] == "not_found"
    assert again.unlink("goal:q3", "team:sales")["removed"] == 1
    assert again.path("goal:q3", "person:asha")["status"] == "not_found"


def test_linker_bad_input():
    linker = CSMLinkerAgent()
    assert linker.link("a", "a")["linked"] is False
    assert linker.link("", "b")["status"] == "invalid_input"
    assert linker.link("a", None)["linked"] is False
    assert linker.unlink("a", "b")["status"] == "not_found"
    assert linker.unlink(["a"], "b")["status"] == "invalid_input"
    assert linker.neighbours("nobody") == [] and linker.path("a", "b")["status"] == "not_found"


def test_policy_generation_is_deterministic_and_checkable():
    p = CSMPolicyAgent()
    policy = p.generate_policy(SPEC)
    assert policy["policy"] == "generated" and [r["check"] for r in policy["rules"]] == ["required", "range", "allowed"]
    assert policy["version"] == p.generate_policy(dict(SPEC))["version"]
    tighter = p.generate_policy({**SPEC, "limits": {"percent": {"max": 10}}})
    assert tighter["version"] != policy["version"]
    assert p.check(policy, {"approver": "asha", "percent": 10, "region": "IN"})["compliant"] is True
    bad = p.check(policy, {"percent": 40, "region": "US"})
    assert bad["compliant"] is False and [v["field"] for v in bad["violations"]] == ["approver", "percent", "region"]
    assert p.check(policy, {"approver": "asha", "percent": "ten"})["violations"][0]["problem"] == "must be a number"
    assert p.check(policy, {"approver": "asha"})["compliant"] is True      # optional fields absent


def test_policy_rejects_empty_or_malformed_specs():
    p = CSMPolicyAgent()
    for bad in ("X", {}, {"name": "empty"}, {"name": "p", "limits": {"x": {}}},
                {"name": "p", "limits": {"x": {"min": 5, "max": 1}}}, {"name": "p", "allowed": {"x": []}},
                {"name": "p", "required": "approver"}):
        r = p.generate_policy(bad)
        assert r["policy"] == "rejected" and r["status"] == "invalid_input"
    assert p.check({"rules": [{"field": "x", "check": "required"}]}, {"x": 1})["compliant"] is False   # not generated
    assert p.check(p.generate_policy(SPEC), "record")["compliant"] is False


def test_core_reviews_goals_with_the_family():
    core = CSMCoreAgent()
    assert core.set_goal("q3_revenue", target=100, total=10, policy=SPEC, owner="team:sales")["status"] == "ok"
    r = core.review("q3_revenue", current=20, elapsed=5, record={"approver": "asha", "percent": 5})
    assert (r["situation"], r["strategy"], r["needs_attention"]) == ("off_track", "escalate", True)
    assert r["compliance"]["compliant"] is True and r["linked"] == [{"item": "team:sales", "relation": "owned_by"}]
    ok = CSMCoreAgent().review("q3_revenue", 80, 7, record={"approver": "asha", "percent": 50})   # new instance
    assert ok["situation"] == "on_track" and ok["needs_attention"] is True                        # policy breach
    assert ok["compliance"]["violations"][0]["field"] == "percent" and ok["reviews"] == 2
    assert core.review("q3_revenue", 80, 7)["compliance"]["compliant"] is False                   # no record given
    assert core.goals() == {"q3_revenue": "on_track"}


def test_core_bad_input():
    core = CSMCoreAgent()
    assert core.set_goal("", 100, 10)["status"] == "invalid_input"
    assert core.set_goal("g", 0, 10)["status"] == "invalid_input"            # target equals start
    assert core.set_goal("g", 100, 10, policy={"name": "empty"})["status"] == "invalid_input"
    assert core.review("ghost", 1, 1)["status"] == "not_found"
    core.set_goal("g", 100, 10)
    assert core.review("g", "lots", 1)["status"] == "invalid_input"
    assert core.review("g", 50, 5)["compliance"] is None and core.goals() == {"g": "on_track"}
