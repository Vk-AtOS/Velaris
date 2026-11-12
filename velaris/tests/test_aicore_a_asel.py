"""ASEL family: strategy choice, scheduling, routing, execution, evaluation."""
import pytest

from velaris.agents.ASEL_EVALUATOR.main import ASEL_EVALUATORAgent
from velaris.agents.ASEL_EXECUTOR.main import ASEL_EXECUTORAgent
from velaris.agents.ASEL_PLANNER.main import ASEL_PLANNERAgent
from velaris.agents.ASEL_ROUTER.main import ASEL_ROUTERAgent
from velaris.agents.ASEL_STRATEGIST.main import ASEL_STRATEGISTAgent


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


OPTIONS = [{"name": "hire", "cost": 90, "impact": 9, "weeks": 12},
           {"name": "outsource", "cost": 45, "impact": 6, "weeks": 4},
           {"name": "automate", "cost": 30, "impact": 7, "weeks": 8}]
CRITERIA = {"cost": {"weight": 2, "direction": "min"}, "impact": {"weight": 1, "direction": "max"}}
TASKS = [{"id": "spec", "duration": 2, "capability": "analysis"},
         {"id": "build", "duration": 5, "depends_on": ["spec"], "capability": "engineering"},
         {"id": "docs", "duration": 1, "depends_on": ["spec"], "capability": "writing"},
         {"id": "launch", "duration": 1, "depends_on": ["build", "docs"], "capability": "engineering"}]


def test_strategist_weighted_choice_with_contributions():
    r = ASEL_STRATEGISTAgent().choose(OPTIONS, CRITERIA)
    assert r["choice"] == "automate"
    top = r["ranking"][0]            # cost best → 2/3; impact (7-6)/(9-6) * 1/3
    assert top["contributions"] == {"cost": 0.6667, "impact": 0.1111} and top["score"] == 0.7778
    assert [x["name"] for x in r["ranking"]] == ["automate", "outsource", "hire"]
    assert r["margin"] == 0.2778 and r["tie"] is False


def test_strategist_constraints_missing_data_and_no_option():
    s = ASEL_STRATEGISTAgent()
    r = s.choose(OPTIONS + [{"name": "wait", "cost": 0}], CRITERIA, [{"field": "weeks", "op": "<=", "value": 6}])
    assert r["choice"] == "outsource" and {e["name"] for e in r["excluded"]} == {"hire", "automate", "wait"}
    none = s.choose(OPTIONS, CRITERIA, [{"field": "weeks", "op": "<", "value": 1}])
    assert none["status"] == "no_option" and none["choice"] is None
    same = s.choose([{"name": "b", "cost": 1, "impact": 1}, {"name": "a", "cost": 1, "impact": 1}], CRITERIA)
    assert same["tie"] is True and same["choice"] == "a"


def test_strategist_bad_input():
    s = ASEL_STRATEGISTAgent()
    assert s.choose("x", CRITERIA)["status"] == "invalid_input"
    assert s.choose(OPTIONS, {})["status"] == "invalid_input"
    assert s.choose(OPTIONS, {"cost": {"weight": -1}})["status"] == "invalid_input"
    assert s.choose(OPTIONS + [OPTIONS[0]], CRITERIA)["status"] == "invalid_input"
    assert s.choose(OPTIONS, CRITERIA, [{"field": "weeks", "op": "about", "value": 1}])["status"] == "invalid_input"


def test_planner_schedule_and_critical_path():
    r = ASEL_PLANNERAgent().plan(TASKS)
    by_id = {s["id"]: s for s in r["steps"]}
    assert r["total_duration"] == 8 and r["critical_path"] == ["spec", "build", "launch"]
    assert (by_id["build"]["start"], by_id["build"]["finish"]) == (2, 7)
    assert by_id["docs"]["slack"] == 4 and by_id["launch"]["start"] == 7
    assert r["levels"] == [["spec"], ["build", "docs"], ["launch"]]


def test_planner_rejects_cycles_and_bad_tasks():
    p = ASEL_PLANNERAgent()
    loop = p.plan([{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}])
    assert loop["status"] == "invalid_plan" and loop["cycle"] == ["a", "b"]
    assert p.plan([{"id": "a", "depends_on": ["ghost"]}])["missing"] == {"a": ["ghost"]}
    assert p.plan([{"id": "a", "duration": -1}])["status"] == "invalid_input"
    assert p.plan([])["status"] == "invalid_input"
    assert p.plan([{"id": "a"}])["total_duration"] == 1          # default duration, single task


def test_router_least_loaded_capable_handler():
    handlers = [{"name": "eng_a", "capabilities": ["engineering"]},
                {"name": "eng_b", "capabilities": ["engineering", "analysis"], "max_steps": 1},
                {"name": "writer", "capabilities": ["writing"]}]
    r = ASEL_ROUTERAgent().route(ASEL_PLANNERAgent().plan(TASKS), handlers)
    assert r["status"] == "ok"
    assert r["routes"] == {"spec": "eng_b", "build": "eng_a", "docs": "writer", "launch": "eng_a"}  # eng_b is capped
    short = ASEL_ROUTERAgent().route(TASKS, handlers[:2])
    assert short["status"] == "partial" and short["unroutable"][0]["id"] == "docs"
    assert short["routes"]["build"] == "eng_a"
    assert ASEL_ROUTERAgent().route(TASKS, [{"name": "x"}])["status"] == "invalid_input"
    assert ASEL_ROUTERAgent().route("steps", handlers)["status"] == "invalid_input"


def test_executor_runs_in_order_and_journals(_data):
    calls = []
    handlers = {"work": lambda step: calls.append(step["id"]) or f"{step['id']} ok"}
    plan = [dict(t, handler="work") for t in reversed(TASKS)]
    r = ASEL_EXECUTORAgent().execute(plan, handlers)
    assert r["status"] == "ok" and calls[0] == "spec" and calls[-1] == "launch"
    assert r["steps"]["build"] == {"state": "done", "handler": "work", "result": "build ok"}
    stored = ASEL_EXECUTORAgent().get_run()["run"]            # new instance reads the journal
    assert stored["run_id"] == r["run_id"] and stored["counts"]["done"] == 4
    assert ASEL_EXECUTORAgent().get_run("nope")["status"] == "not_found"


def test_executor_failure_approval_and_missing_handler_stop_dependents():
    def boom(step):
        raise RuntimeError("supplier API down")
    plan = [{"id": "a", "handler": "ok"}, {"id": "b", "handler": "boom", "depends_on": ["a"]},
            {"id": "c", "handler": "ok", "depends_on": ["b"]}, {"id": "d", "handler": "ok", "depends_on": ["a"]},
            {"id": "pay", "handler": "ok", "requires_approval": True}, {"id": "e", "handler": "ghost"}]
    ex = ASEL_EXECUTORAgent()
    r = ex.execute(plan, {"ok": lambda s: 1, "boom": boom})
    states = {sid: o["state"] for sid, o in r["steps"].items()}
    assert states == {"a": "done", "b": "failed", "c": "skipped", "d": "done", "pay": "blocked", "e": "blocked"}
    assert r["status"] == "partial" and "supplier API down" in r["steps"]["b"]["error"]
    assert ex.execute(plan, {"ok": lambda s: 1, "boom": boom}, approved=["pay"])["steps"]["pay"]["state"] == "done"


def test_executor_bad_input():
    ex = ASEL_EXECUTORAgent()
    assert ex.execute("plan", {})["status"] == "invalid_input"
    assert ex.execute([{"id": "a"}], {"h": "not callable"})["status"] == "invalid_input"
    assert ex.execute([{"id": "a", "depends_on": ["a"]}], {})["status"] == "invalid_plan"
    assert ex.execute([{"id": "a"}, {"id": "a"}], {})["status"] == "invalid_input"


def test_evaluator_verdicts():
    ev = ASEL_EVALUATORAgent()
    done = {"steps": {"a": {"state": "done"}, "b": {"state": "done"}}}
    half = {"steps": {"a": {"state": "done"}, "b": {"state": "failed", "error": "boom"}}}
    targets = {"revenue": {"target": 100, "direction": "max", "tolerance": 0.1},
               "cost": {"target": 50, "direction": "min"}}
    assert ev.evaluate(done, targets, {"revenue": 120, "cost": 50})["verdict"] == "met"
    near = ev.evaluate(done, targets, {"revenue": 95, "cost": 40})
    assert near["verdict"] == "partial" and near["kpis"]["revenue"] == {
        "result": "within_tolerance", "target": 100.0, "actual": 95.0, "shortfall": 5.0}
    assert ev.evaluate(done, targets, {"revenue": 120, "cost": 51})["verdict"] == "missed"    # no tolerance on cost
    unmeasured = ev.evaluate(done, targets, {"revenue": 120})
    assert unmeasured["verdict"] == "missed" and "cost: not measured" in unmeasured["gaps"]
    r = ev.evaluate(half)
    assert r["verdict"] == "partial" and r["completion"] == 0.5 and "step b: failed (boom)" in r["gaps"]
    assert ev.evaluate({"steps": {"a": {"state": "blocked"}}})["verdict"] == "missed"
    assert ev.evaluate({"steps": {}})["verdict"] == "missed"


def test_evaluator_bad_input():
    ev = ASEL_EVALUATORAgent()
    assert ev.evaluate(None)["status"] == "invalid_input"
    assert ev.evaluate({"steps": {"a": {"state": "done"}}}, {"x": {"target": "high"}})["status"] == "invalid_input"


def test_family_pipeline_strategy_to_verdict():
    choice = ASEL_STRATEGISTAgent().choose(OPTIONS, CRITERIA)["choice"]
    plan = ASEL_PLANNERAgent().plan(TASKS)
    routed = ASEL_ROUTERAgent().route(plan, [{"name": "team", "capabilities": ["analysis", "engineering", "writing"]}])
    run = ASEL_EXECUTORAgent().execute(routed, {"team": lambda step: {"did": step["id"], "for": choice}})
    verdict = ASEL_EVALUATORAgent().evaluate(run, {"weeks": {"target": 8, "direction": "min"}},
                                             {"weeks": plan["total_duration"]})
    assert run["steps"]["launch"]["result"] == {"did": "launch", "for": "automate"}
    assert verdict["verdict"] == "met" and verdict["completion"] == 1.0
