"""KAN-106 (_ai_core agents): crashes and wrong results found by the verification pass."""
from importlib import import_module


from velaris.core.access import Caller, acting_as


def agent(name, cls=None):
    mod = import_module(f"velaris.agents.{name}.main")
    return getattr(mod, cls or f"{name}Agent")()


def test_vpse_scenario_bad_function_arguments_do_not_raise():
    v = agent("VPSE_SCENARIO")
    assert v.run({"x": 1}, {"o": "abs()"})["status"] != "ok"
    assert v.run({"x": 1}, {"o": "round(1, 2, 3)"})["status"] != "ok"
    assert v.run({"x": -2}, {"o": "abs(x)"})["base"] == {"o": 2.0}


def test_mrf_eval_empty_check_list_is_invalid_not_division_by_zero():
    r = agent("MRF_EVAL").evaluate("hi", {"required": []})
    assert r["status"] == "invalid_input" and r["passed"] is False


def test_csg_statealign_round_trips_when_a_field_changes_shape():
    c = agent("CSG_STATEALIGN")
    for expected, actual in [({"x": {"y": 1}}, {"x": 1}), ({"x": 1}, {"x": {"y": 1}}), ({"x": {"y": 1}}, {"x": {}}),
                             ({"x": {}}, {"x": {"y": 1}}), ({"x": {}}, {"x": 1}), ({"x": 1}, {"x": {}})]:
        patch = c.align(expected, actual)["patch"]
        assert c.apply(actual, patch)["state"] == expected, (expected, actual)


def test_self_correction_clamps_with_only_a_minimum_or_only_a_maximum():
    e = import_module("velaris.agents.SELF_CORRECTION_ENGINE.main").SelfCorrectionEngine()
    low = e.correct({"n": 1}, {"n": {"type": "number", "min": 5}})
    assert low["corrected"]["n"] == 5
    high = e.correct({"n": 99}, {"n": {"type": "number", "max": 10}})
    assert high["corrected"]["n"] == 10


def test_intent_negation_is_not_a_destructive_request():
    s = import_module("velaris.agents.INTENT_SYNTHESIZER.main")
    synth = [v for v in vars(s).values() if isinstance(v, type) and v.__module__ == s.__name__][0]()
    out = synth.synthesize("do not delete the invoices")["intent"]
    assert out["action"] is None and out["risk"] is None and out["prohibited_action"] == "delete"
    assert synth.synthesize("delete the invoices")["intent"]["risk"] == "destructive"


def test_alk_evo_rollback_sticks_and_min_samples_zero_works():
    alk = import_module("velaris.agents.ALK_EVO.main").ALK_EVOAgent(min_samples=0)
    alk.register("a", {}), alk.register("b", {})
    alk.record("a", 1.0), alk.record("b", 2.0)
    assert alk.evaluate()["promoted"] is True and alk.champion()["champion"] == "b"
    alk.rollback()
    assert alk.evaluate()["promoted"] is False and alk.champion()["champion"] == "a"


def test_crk_intent_unhashable_model_reply_is_unresolved():
    mod = import_module("velaris.agents.CRK_INTENT.main")
    cls = [v for v in vars(mod).values() if isinstance(v, type) and v.__module__ == mod.__name__][0]
    a = cls()

    class LLM:
        def complete(self, *args, **kwargs):
            return type("R", (), {"text": '{"intent": ["x"]}'})()
    r = a._ask(LLM(), "something", [])
    assert r["status"] == "unresolved"


def test_tasker_rejects_cycles_and_non_string_ids():
    t = import_module("velaris.agents.SELF_DIRECTED_TASKER.main").SelfDirectedTasker()
    cyc = {"tasks": [{"id": "a"}, {"id": "b", "depends_on": ["c"]}, {"id": "c", "depends_on": ["b"]}]}
    assert t.prepare(cyc)["status"] == "deadlocked" and t.start(cyc)["status"] == "deadlocked"
    assert t.prepare({"tasks": [{"id": 1}, {"id": 2, "depends_on": [1]}]})["status"] == "invalid_input"


def test_schedulon_zero_workers_and_personality_banned_words_are_whole_words():
    s = import_module("velaris.agents.SCHEDULON.main").SchedulonAgent()
    assert s.distribute_load([1, 2], 0) == [] and s.distribute_load([1, 2], -1) == []
    p = agent("PERSONALITY_MOD")
    with acting_as(Caller("u", "kf", frozenset({"governance_admin"}))):
        assert p.update({"banned": ["ass"]})["updated"] is True
    out = p.apply("The class is an ass")
    assert "class" in out["text"] and "ass" not in out["text"].replace("class", "")


def test_neural_mesh_says_queued_not_delivered():
    m = import_module("velaris.agents.NEURAL_MESH.main").NeuralMesh()
    r = m.route("a", "b", {"x": 1})
    assert r["ok"] is True and r["queued"] is True and r["delivered"] is False
    assert m.receive("b") == [{"from": "a", "payload": {"x": 1}}] and m.receive("b") == []
    assert m.route("a", "", {"x": 1})["ok"] is False
    assert all(v["queued"] for v in m.broadcast(["c", "d"], {"y": 2}).values())


def test_meta_reasoning_solve_survives_an_invalid_evaluation(monkeypatch):
    mod = import_module("velaris.agents.META_REASONING_CORE.main")
    cls = [v for v in vars(mod).values() if isinstance(v, type) and v.__module__ == mod.__name__][0]
    core = cls()
    monkeypatch.setattr(core.evaluator, "evaluate", lambda *a, **k: {"status": "invalid_input", "reason": "x"})
    monkeypatch.setattr(mod, "model_or_none", lambda llm: object())
    monkeypatch.setattr(mod, "ask_json", lambda *a, **k: ({"answer": "draft"}, None))
    r = core.solve("task", {"required": ["x"]})
    assert r["status"] == "invalid_input" and r["answer"] is None


def test_adaptive_action_engine_refused_request_is_not_recorded_as_a_failed_outcome():
    mod = import_module("velaris.agents.ADAPTIVE_ACTION_ENGINE.main")
    eng = mod.ADAPTIVE_ACTION_ENGINEAgent()
    recorded = []
    eng.outcomes.record = lambda *a: recorded.append(a)
    eng.choose = lambda s, c: {"status": "ok", "order": [{"type": "t"}], "ranking": []}
    eng.runtime.run = lambda action, by: {"status": "no_request", "reason": "approve an action someone requested"}
    r = eng.act("s", [{"type": "t", "id": "1"}])
    assert recorded == [] and r["status"] == "no_action"
