"""AIIE kernel and the planning/decision agents around it."""
import pytest

from velaris.agents.ACTION_MODELING_CORE.main import ActionModelingCore
from velaris.agents.AIIE_KERNEL.main import PIPELINE, AIIEKernel
from velaris.agents.CAUSALITY_RESOLVER.main import CausalityResolver
from velaris.agents.DECISION_COLLAPSE_ENGINE.main import DecisionCollapseEngine
from velaris.agents.DECISION_GRAPH_ENGINE.main import DecisionGraphEngine
from velaris.intel import trace

ACTIONS = [{"name": "ship", "needs": ["paid", "packed"], "gives": ["shipped"]},
           {"name": "pack", "needs": ["order"], "gives": ["packed"]},
           {"name": "invoice", "needs": ["order"], "gives": ["invoiced"]},
           {"name": "collect", "needs": ["invoiced"], "gives": ["paid"]}]


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_action_model_orders_by_preconditions():
    r = ActionModelingCore().model({"intent": "fulfil_order", "actions": ACTIONS, "state": ["order"]})
    assert r["status"] == "ok" and r["plan"] == ["pack", "invoice", "collect", "ship"]
    deps = {s["id"]: s["depends_on"] for s in r["steps"]}
    assert deps == {"pack": [], "invoice": [], "collect": ["invoice"], "ship": ["collect", "pack"]}
    assert "shipped" in r["final_state"]


def test_action_model_reports_blocked_actions_and_uses_playbooks():
    r = ActionModelingCore().model({"intent": "fulfil_order", "actions": ACTIONS, "state": []})
    assert r["status"] == "partial" and r["plan"] == []
    assert {"action": "ship", "missing": ["packed", "paid"]} in r["blocked"]
    book = ActionModelingCore(playbooks={"fulfil_order": ACTIONS})
    assert book.model({"intent": "fulfil_order", "state": ["order"]})["plan"][-1] == "ship"
    none = book.model({"intent": "refined_goal", "source": {}})
    assert none["status"] == "no_actions" and none["plan"] == []          # never invents steps


def test_action_model_bad_input():
    m = ActionModelingCore().model
    assert m("ship it")["status"] == "invalid_input" and m("ship it")["plan"] == []
    assert m({"actions": []})["status"] == "invalid_input"
    assert m({"actions": [{"name": "a"}, {"name": "a"}]})["status"] == "invalid_input"
    assert m({"actions": [{"name": "a", "needs": "x"}]})["status"] == "invalid_input"
    assert m({"actions": [{"name": "a"}], "state": "order"})["status"] == "invalid_input"


def test_graph_from_steps_and_from_a_sequence():
    plan = ActionModelingCore().model({"actions": ACTIONS, "state": ["order"]})
    g = DecisionGraphEngine().graph(plan)["graph"]
    assert g["levels"] == [["invoice", "pack"], ["collect"], ["ship"]]
    assert g["edges"] == [["collect", "ship"], ["invoice", "collect"], ["pack", "ship"]]
    assert g["roots"] == ["invoice", "pack"] and g["leaves"] == ["ship"]
    seq = DecisionGraphEngine().graph({"plan": ["a", "b", "c"]})["graph"]
    assert seq["steps"] == ["a", "b", "c"] and seq["edges"] == [["a", "b"], ["b", "c"]]


def test_graph_refuses_cycles_and_bad_plans():
    g = DecisionGraphEngine().graph
    loop = g({"steps": [{"id": "a", "depends_on": ["b"]}, {"id": "b", "depends_on": ["a"]}]})
    assert loop["status"] == "invalid_plan" and loop["cycle"] == ["a", "b"] and loop["graph"]["steps"] == []
    assert g({"steps": [{"id": "a", "depends_on": ["zz"]}]})["missing"] == {"a": ["zz"]}
    assert g({"plan": []})["status"] == "empty" and g({})["status"] == "empty"
    assert g("plan")["status"] == "invalid_input" and g({"steps": [{"id": "a"}, {"id": "a"}]})["status"] == "invalid_input"
    assert g({"plan": [1, 2]})["status"] == "invalid_input"


def test_kernel_runs_stages_in_order_and_traces():
    stages = [("model", ActionModelingCore().model), ("graph", DecisionGraphEngine().graph)]
    r = AIIEKernel().run({"actions": ACTIONS, "state": ["order"]}, stages)
    assert r["status"] == "ok" and r["completed"] == ["model", "graph"] and r["unverified"] == []
    assert r["output"]["graph"]["leaves"] == ["ship"]
    last = list(trace.entries())[-1]
    assert (last["actor"], last["action"]) == ("AIIE_KERNEL", "pipeline.completed")


def test_kernel_halts_on_failed_raising_or_malformed_stages():
    k = AIIEKernel()
    stages = [("model", ActionModelingCore().model), ("graph", DecisionGraphEngine().graph)]
    halted = k.run({"intent": "nothing to do"}, stages)
    assert halted["status"] == "halted" and halted["halted_at"] == "model" and halted["completed"] == []
    assert "no_actions" in halted["reason"]

    def boom(value):
        raise KeyError("missing")
    r = k.run({}, [("echo", lambda v: {"x": 1}), ("boom", boom), ("never", lambda v: {"status": "ok"})])
    assert (r["halted_at"], r["completed"], r["unverified"]) == ("boom", ["echo"], ["echo"])
    assert k.run({}, [("text", lambda v: "done")])["reason"] == "stage did not return an object"
    assert k.run("idea")["status"] == "invalid_input" and k.run({}, [])["status"] == "invalid_input"
    assert k.run({}, [("x", "not callable")])["status"] == "invalid_input"


def test_kernel_default_pipeline_never_reports_a_clean_run_it_cannot_verify():
    r = AIIEKernel().run({"context": {"x": 1}})
    labels = [p for p, _, _ in PIPELINE]
    assert r["status"] in ("ok", "halted") and r["completed"] == labels[:len(r["completed"])]
    if r["status"] == "halted":
        assert r["halted_at"] in labels
    else:                                           # every stage either said "ok" or is listed as unverified
        assert set(r["unverified"]) <= set(labels)


def test_collapse_picks_by_expected_value_or_declines():
    options = [{"name": "expand", "score": 100, "probability": 0.3}, {"name": "hold", "score": 40, "probability": 0.9},
               {"name": "exit", "score": 10}]
    r = DecisionCollapseEngine().collapse({"options": options})
    assert r["final_decision"] == "hold" and r["expected"] == 36 and r["margin"] == 6
    assert [x["name"] for x in r["ranking"]] == ["hold", "expand", "exit"]
    close = DecisionCollapseEngine(min_margin=10).collapse(options)
    assert close["status"] == "undecided" and close["final_decision"] is None and close["contenders"] == ["hold", "expand"]
    tie = DecisionCollapseEngine().collapse([{"name": "a", "score": 1}, {"name": "b", "score": 1}])
    assert tie["status"] == "undecided" and tie["final_decision"] is None
    assert DecisionCollapseEngine().collapse([{"name": "only", "score": 1}])["final_decision"] == "only"


def test_collapse_bad_input():
    c = DecisionCollapseEngine().collapse
    for bad in (None, [], {"options": []}, [{"name": "a"}], [{"name": "a", "score": 1, "probability": 2}],
                [{"name": "a", "score": 1}, {"name": "a", "score": 2}]):
        r = c(bad)
        assert r["status"] == "invalid_input" and r["final_decision"] is None


def test_causality_merges_paths_and_ranks_root_causes():
    paths = [["supplier late", "stock-out", "missed delivery"], ["supplier late", "stock-out", "missed delivery"],
             ["forecast error", "stock-out", "missed delivery"], ["driver shortage", "missed delivery"]]
    r = CausalityResolver().resolve(paths)["resolved"]
    assert r["effect"] == "missed delivery" and r["final_effects"] == ["missed delivery"]
    assert r["root_causes"] == [{"cause": "supplier late", "paths": 2, "share": 0.5},
                                {"cause": "driver shortage", "paths": 1, "share": 0.25},
                                {"cause": "forecast error", "paths": 1, "share": 0.25}]
    assert {"cause": "stock-out", "effect": "missed delivery", "reports": 3} in r["links"]
    assert r["order"].index("supplier late") < r["order"].index("stock-out") < r["order"].index("missed delivery")
    mid = CausalityResolver().resolve(paths, effect="stock-out")["resolved"]
    assert [c["cause"] for c in mid["root_causes"]] == ["supplier late", "forecast error"]


def test_causality_contradictions_and_bad_input():
    res = CausalityResolver().resolve
    clash = res([["churn", "low revenue"], ["low revenue", "churn"]])
    assert clash["status"] == "contradiction" and clash["events"] == ["churn", "low revenue"] and clash["resolved"] is None
    assert res([["a", "a"]])["status"] == "invalid_input"
    assert res([["a"]])["status"] == "invalid_input" and res("a->b")["status"] == "invalid_input"
    assert res([["a", "b"]], effect="zzz")["status"] == "not_found"
    two = res([["a", "b"], ["c", "d"]])["resolved"]
    assert two["effect"] is None and two["root_causes"] is None and two["final_effects"] == ["b", "d"]
