"""KAN-93 leftovers: MEMORY_REALLOCATOR, STREAM_PROCESSOR, CHROMOS, OPPORTUNITY_RADAR, PROBABILIS, STOCHASTIX, MEETING_SUMMARIZER."""
from importlib import import_module

import pytest

from velaris.intel.llm import FakeLLM


def agent(name):
    return import_module(f"velaris.agents.{name}.main")


def test_memory_reallocator_saves_an_overcommitted_plan_too():
    M = agent("MEMORY_REALLOCATOR")
    a = M.MEMORY_REALLOCATORAgent() if hasattr(M, "MEMORY_REALLOCATORAgent") else next(getattr(M, n)() for n in dir(M) if n.endswith("Agent"))
    a.set_consumer("db", 800, 1)
    a.set_consumer("cache", 400, 1)
    out = a.reallocate(total_mb=600)
    assert out["overcommitted"] is True
    assert a._state.load()["last_plan"]["plan"] == out["plan"]                 # it used to return before saving


def test_stream_processor_never_evicts_an_open_window(monkeypatch):
    M = agent("STREAM_PROCESSOR")
    monkeypatch.setattr(M, "MAX_WINDOWS", 3)
    s = M.STREAM_PROCESSORAgent()
    s.define("s", 10, "v", lateness_s=0)
    s.ingest("s", [{"ts": 1, "v": 1}, {"ts": 11, "v": 1}, {"ts": 21, "v": 1}])           # three windows, the last one open
    r = s.ingest("s", [{"ts": 31, "v": 1}, {"ts": 41, "v": 1}])                            # two more: closed ones make room
    assert r["accepted"] == 2 and r.get("overflow", 0) == 0
    open_starts = [w["start"] for w in s.results("s", closed_only=False)["windows"]]
    assert 41 // 10 * 10 in open_starts and 31 // 10 * 10 in open_starts                  # the newest, open windows are kept
    s.define("t", 1000, "v", key_field="k", lateness_s=1e9)                                # nothing ever closes: all windows stay open
    s.ingest("t", [{"ts": 1, "v": 1, "k": str(i)} for i in range(3)])
    r = s.ingest("t", [{"ts": 1, "v": 1, "k": "new"}])
    assert r["accepted"] == 0 and r["overflow"] == 1                                       # refused, no open data was dropped
    assert len(s.results("t", closed_only=False)["windows"]) == 3


def test_chromos_unknown_key_is_not_unchanged_and_hashes_survive_a_restart():
    C = agent("CHROMOS")
    c = C.ChromosAgent()
    with pytest.raises(KeyError):
        c.compare_schema("nope", {"a": 1})
    c.store_schema("m", {"a": 1})
    assert C.ChromosAgent().compare_schema("m", {"a": 1}) is False                         # a new instance (a restart) still knows it
    assert C.ChromosAgent().compare_schema("m", {"a": 2}) is True


def test_opportunity_radar_counts_untracked_results_apart_from_seen_before(monkeypatch):
    O = agent("OPPORTUNITY_RADAR")
    monkeypatch.setattr(O, "MAX_SEEN", 1)
    radar = next(getattr(O, n)() for n in dir(O) if n.endswith("Agent") and n != "Agent")
    fake = lambda q, limit=8: [{"title": "a", "url": "https://x.test/1", "snippet": "s"}, {"title": "b", "url": "https://x.test/2", "snippet": "s"}]
    out = radar.run({"queries": ["q"], "keywords": []}, search_fn=fake)
    assert out["status"] in ("ok", "no_results") and len(out["new"]) == 1 and out["untracked"] == 1 and out["seen_before"] == 0
    again = radar.run({"queries": ["q"], "keywords": []}, search_fn=fake)
    assert again["seen_before"] == 1 and again["untracked"] == 1 and again["new"] == []


def test_stochastix_is_bounded_and_has_drift():
    S = agent("STOCHASTIX")
    a = S.StochastixAgent({"steps": 5})
    with pytest.raises(ValueError):
        a.sample_paths(n_paths=S.MAX_PATHS + 1)
    assert S.StochastixAgent({"steps": 10**9}).steps == S.MAX_STEPS
    up = a.random_walk(step_std=0.0, drift=2.0)
    assert up == [0.0, 2.0, 4.0, 6.0, 8.0]


def test_probabilis_refuses_a_name_instead_of_a_function_and_bounds_trials():
    P = agent("PROBABILIS")
    p = P.ProbabilisAgent({"trials": 10**12})
    assert p.trials == P.MAX_TRIALS
    with pytest.raises(TypeError):
        p.monte_carlo("os.system")
    from velaris.api import allowlist
    assert allowlist.rule_for("PROBABILIS", "monte_carlo") is None                         # never callable over HTTP


def test_meeting_summarizer_uses_the_model_through_the_router_at_restricted_sensitivity():
    M = agent("MEETING_SUMMARIZER")
    llm = FakeLLM(lambda prompt, model: "We agreed to ship on Friday. Asha owns the release.")
    s = M.MeetingSummarizer({"llm": llm})
    t = {"text": "We decided to ship on Friday. Asha will own the release.", "segments": [{"text": "We decided to ship on Friday."}]}
    out = s.summarize(t, {"title": "Release sync"})
    assert out["summary"].startswith("We agreed") and out["llm_status"] == "ok" and "decided" in out["extractive_summary"]
    assert llm.calls and llm.calls[0]["sensitivity"] == "restricted" and llm.calls[0]["purpose"] == "meeting_summary"
    broken = M.MeetingSummarizer({"llm": FakeLLM({})}).summarize(t)                         # a failing model keeps the extractive summary
    assert broken["llm_status"] == "model_error" and broken["summary"] == broken["extractive_summary"]
    assert M.MeetingSummarizer().summarize(t)["llm_status"] == "not_used"
