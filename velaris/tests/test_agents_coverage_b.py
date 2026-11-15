"""Behaviour of twelve small agents: creativity, search, stability, LYRA, sales,
owner verification, PIN unlock, successor key, document library, business ops,
marketing and economic intelligence. Offline; VELARIS_DATA is isolated per test."""
from importlib import import_module

import pytest

from velaris.core.access import Caller, acting_as


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def make(name, cls):
    return getattr(import_module(f"velaris.agents.{name}.main"), cls)()


# ── NEURAL_CREATIVITY_ENGINE ─────────────────────────────────────────────────
def test_NEURAL_CREATIVITY_ENGINE_blends_one_item_from_each_pool():
    e = make("NEURAL_CREATIVITY_ENGINE", "NeuralCreativityEngine")
    assert e.add_to_pool("OBJECTS", "lamp") is True       # pool name is case-insensitive
    assert e.add_to_pool("objects", "lamp") is False      # duplicate refused
    assert e.add_to_pool("moods", "x") is False           # unknown pool refused
    e.add_to_pool("actions", "juggling")
    e.add_to_pool("styles", "baroque")
    assert e.generate() == {"object": "lamp", "action": "juggling", "style": "baroque",
                            "concept": "lamp performing juggling in baroque style"}
    assert e.pool_list()["objects"] == ["lamp"]


def test_NEURAL_CREATIVITY_ENGINE_reports_first_empty_pool_and_pool_list_is_a_copy():
    e = make("NEURAL_CREATIVITY_ENGINE", "NeuralCreativityEngine")
    assert e.generate() == {"error": "pool_empty:objects"}
    e.add_to_pool("objects", "lamp")
    assert e.generate() == {"error": "pool_empty:actions"}
    e.pool_list()["objects"].append("tampered")
    assert e.pool_list()["objects"] == ["lamp"]


# ── ADVANCED_SEARCH_ENGINE ───────────────────────────────────────────────────
def test_ADVANCED_SEARCH_ENGINE_ranks_records_by_number_of_matching_fields():
    s = make("ADVANCED_SEARCH_ENGINE", "AdvancedSearchEngine")
    assert s.register_dataset("Staff") is True
    assert s.register_dataset("staff") is False           # same name, any case
    assert s.datasets_list() == ["staff"]
    s.add_record("STAFF", {"name": "Asha Rao", "role": "finance"})
    s.add_record("staff", {"name": "Finance Bot", "team": "finance ops", "note": "FINANCE"})
    s.add_record("staff", {"name": "Ravi", "role": "sales"})
    hits = s.search("Finance")
    assert [(h["record"]["name"], h["score"], h["dataset"]) for h in hits] == [
        ("Finance Bot", 3, "staff"), ("Asha Rao", 1, "staff")]


def test_ADVANCED_SEARCH_ENGINE_unknown_dataset_and_no_match_give_nothing():
    s = make("ADVANCED_SEARCH_ENGINE", "AdvancedSearchEngine")
    assert s.add_record("ghost", {"a": 1}) is False
    assert s.search("anything") == []
    s.register_dataset("d")
    s.add_record("d", {"a": 1})
    assert s.search("zzz") == []
    assert s.search("1")[0]["score"] == 1                 # non-string values are stringified


def test_ADVANCED_SEARCH_ENGINE_web_search_delegates_to_the_web_module(monkeypatch):
    s = make("ADVANCED_SEARCH_ENGINE", "AdvancedSearchEngine")
    monkeypatch.setattr("velaris.agents.ADVANCED_SEARCH_ENGINE.main.web.search",
                        lambda q, limit=8: [{"q": q, "limit": limit}])
    assert s.web_search("rates", limit=3) == [{"q": "rates", "limit": 3}]


# ── LONG_RUN_STABILITY_SIMULATOR ─────────────────────────────────────────────
def test_LONG_RUN_STABILITY_SIMULATOR_scores_flat_noisy_and_degenerate_series():
    sim = make("LONG_RUN_STABILITY_SIMULATOR", "LongRunStabilitySimulator")
    assert sim.simulate([10, 10, 10]) == {"stability": 100.0, "variance": 0, "failure_prob": 0.0}
    noisy = sim.simulate([0, 10])                          # pvariance 25, drift 10
    assert noisy == {"stability": 0.0, "variance": 25, "failure_prob": 0.35}
    assert sim.simulate([]) == {"stability": 0, "variance": 0, "failure_prob": 1.0}
    assert sim.simulate([7]) == {"stability": 100, "variance": 0, "failure_prob": 0.0}
    assert sim.summary()["runs"] == 2                      # empty and single runs are not recorded


def test_LONG_RUN_STABILITY_SIMULATOR_summary_averages_and_empty_summary():
    sim = make("LONG_RUN_STABILITY_SIMULATOR", "LongRunStabilitySimulator")
    assert sim.summary() == {"runs": 0, "avg_stability": 0, "avg_failure_prob": 0}
    out = sim.batch_simulate([[5, 5], [0, 10]])
    assert [o["stability"] for o in out] == [100.0, 0.0]
    assert sim.summary() == {"runs": 2, "avg_stability": 50.0, "avg_failure_prob": 0.175}


# ── LYRA ─────────────────────────────────────────────────────────────────────
def test_LYRA_presets_switch_and_unknown_preset_is_refused():
    ly = make("LYRA", "LyraEngine")
    assert ly.transform("hi") == "hi"                      # neutral by default
    assert ly.set_preset("warm") is True
    assert ly.transform("hi") == "✨ hi ✨"
    assert ly.set_preset("shouty") is False
    assert ly.active_preset == "warm"                      # unchanged by the refusal


def test_LYRA_technical_preset_puts_the_tag_on_its_own_line():
    ly = make("LYRA", "LyraEngine")
    ly.set_preset("technical")
    assert ly.transform("body") == "[TECH]\nbody"


# ── AUTONOMOUS_SALES_NAVIGATOR ───────────────────────────────────────────────
def test_AUTONOMOUS_SALES_NAVIGATOR_scores_ranks_and_picks_strategy():
    n = make("AUTONOMOUS_SALES_NAVIGATOR", "AutonomousSalesNavigator")
    hot = n.add_lead("Hot", 90, 80, 70)                    # 36 + 24 + 21 = 81
    warm = n.add_lead("Warm", 60, 60, 60)                  # 60
    cold = n.add_lead("Cold", 10, 10, 10)                  # 10
    assert [n.score_lead(x) for x in (hot, warm, cold)] == [81, 60, 10]
    assert n.suggest_strategy(hot) == "High-touch call and proposal"
    assert n.suggest_strategy(warm) == "Email sequence + call"
    assert n.suggest_strategy(cold) == "Nurture with periodic content"
    assert n.predict_close_probability(hot) == 0.81
    assert [x["name"] for x in n.top_leads(2)] == ["Hot", "Warm"]


def test_AUTONOMOUS_SALES_NAVIGATOR_caps_probability_and_handles_empty_and_bad_leads():
    n = make("AUTONOMOUS_SALES_NAVIGATOR", "AutonomousSalesNavigator")
    assert n.top_leads(3) == []
    assert n.predict_close_probability({"budget": 500, "interest": 500, "fit": 500}) == 1.0
    with pytest.raises(KeyError):                          # a lead without a 'fit' is not scored
        n.score_lead({"budget": 1, "interest": 1})


# ── OWNER_VERIFICATION ───────────────────────────────────────────────────────
def test_OWNER_VERIFICATION_needs_all_three_factors_to_match_and_stores_only_hashes():
    o = make("OWNER_VERIFICATION", "OwnerVerification")
    assert o.verify("f", "c", "v") is False                # nobody enrolled: fail closed
    o.enroll("finger-1", "face-1", "voice-1")
    assert "finger-1" not in str(o.owner_templates)
    assert o.verify("finger-1", "face-1", "voice-1") is True
    assert o.verify("finger-1", "face-1", "voice-X") is False
    assert o.verify("", "", "") is False


def test_OWNER_VERIFICATION_partial_verify_fails_closed():
    o = make("OWNER_VERIFICATION", "OwnerVerification")
    assert o.partial_verify(finger="x") is False           # not enrolled
    o.enroll("finger-1", "face-1", "voice-1")
    assert o.partial_verify(finger="finger-1") is True
    assert o.partial_verify(finger="finger-1", face="wrong") is False
    assert o.partial_verify(iris="x") is False             # unknown factor
    assert o.partial_verify() is False                     # no factor presented
    o.enroll("other", "other", "other")                    # single owner: re-enrol replaces
    assert o.partial_verify(finger="finger-1") is False


# ── PIN_UNLOCK_LAYER ─────────────────────────────────────────────────────────
def test_PIN_UNLOCK_LAYER_registers_locked_unlocks_with_right_pin_and_relocks():
    p = make("PIN_UNLOCK_LAYER", "PINUnlockLayer")
    assert p.register_pin("asha", "4821") is True
    assert p.register_pin("asha", "0000") is False         # cannot overwrite
    assert p.is_locked("asha") is True
    assert p.unlock("asha", "0000") is False and p.is_locked("asha") is True
    assert p.unlock("asha", "4821") is True and p.is_locked("asha") is False
    p.lock("asha")
    assert p.is_locked("asha") is True
    assert "4821" not in p.pins["asha"]


def test_PIN_UNLOCK_LAYER_unknown_user_cannot_unlock_and_reads_as_locked():
    p = make("PIN_UNLOCK_LAYER", "PINUnlockLayer")
    assert p.unlock("ghost", "1234") is False
    assert p.is_locked("ghost") is True
    p.lock("ghost")                                        # no-op, no crash
    assert p.locked == {}


# ── SUCCESSOR_KEY_MODULE ─────────────────────────────────────────────────────
def test_SUCCESSOR_KEY_MODULE_key_is_set_once_verified_and_wiped():
    k = make("SUCCESSOR_KEY_MODULE", "SuccessorKeyModule")
    assert k.has_key() is False and k.verify("anything") is False
    assert k.set_successor_key("heir-key") is True
    assert k.set_successor_key("other") is False           # no overwrite without a wipe
    assert k.verify("heir-key") is True and k.verify("other") is False
    assert "heir-key" not in k.successor_hash
    k.wipe_key()
    assert k.has_key() is False and k.verify("heir-key") is False
    assert k.set_successor_key("new-key") is True


# ── DOCUMENT_LIBRARY ─────────────────────────────────────────────────────────
def test_DOCUMENT_LIBRARY_ingest_search_is_scoped_and_empty_library_answers_nothing():
    lib = make("DOCUMENT_LIBRARY", "DocumentLibrary")
    assert lib.health_check() == {"agent": "DOCUMENT_LIBRARY", "status": "ok"}
    with acting_as(Caller("asha", "kf")):
        r = lib.ingest("policy.txt", b"The refund window is 30 days for all orders.", scope="acme")
        assert r["action"] == "ADDED" and r["passages"] == 1 and r["format"] == "text"
        hits = lib.search("refund window", "acme")
        assert [h["document"] for h in hits] == ["policy.txt"]
        assert "30 days" in hits[0]["text"]
        assert lib.search("refund window", "rival") == []   # another tenant's scope sees nothing
        assert lib.ask("what is the refund window?", "rival") == {
            "answer": "", "sources": [], "unsupported": [],
            "reason": "nothing relevant in the library"}


# ── BUSINESS_OPS_ENGINE ──────────────────────────────────────────────────────
def test_BUSINESS_OPS_ENGINE_tracks_tasks_and_kpis_in_the_summary():
    b = make("BUSINESS_OPS_ENGINE", "BusinessOpsEngine")
    assert b.summarize() == {"total": 0, "completed": 0, "pending": 0, "kpis": {}}
    assert b.add_task("ship", {"n": 1}) == {"name": "ship", "params": {"n": 1}, "status": "PENDING"}
    b.add_task("bill", {})
    assert b.complete_task("ship") is True
    b.set_kpi("nps", 41.5)
    assert b.get_kpi("nps") == 41.5
    assert b.summarize() == {"total": 2, "completed": 1, "pending": 1, "kpis": {"nps": 41.5}}
    assert [t["status"] for t in b.list_tasks()] == ["DONE", "PENDING"]


def test_BUSINESS_OPS_ENGINE_unknown_task_and_kpi_are_harmless():
    b = make("BUSINESS_OPS_ENGINE", "BusinessOpsEngine")
    assert b.complete_task("ghost") is False
    assert b.get_kpi("ghost") == 0.0
    b.list_tasks().append({"name": "x"})                   # list is a copy
    assert b.list_tasks() == []


# ── AUTONOMOUS_MARKETING_ENGINE ──────────────────────────────────────────────
def test_AUTONOMOUS_MARKETING_ENGINE_campaign_is_recorded_with_per_channel_strategy():
    m = make("AUTONOMOUS_MARKETING_ENGINE", "AutonomousMarketingEngine")
    assert m.get_history() == []
    c = m.generate_campaign("Chai", "students", 5000)
    assert c["strategy"] == {"email": "Email sequence for students",
                             "social": "Social ads targeting students",
                             "landing_page": "Landing page optimized for Chai"}
    assert (c["product"], c["audience"], c["budget"]) == ("Chai", "students", 5000)
    assert m.get_history() == [c]


def test_AUTONOMOUS_MARKETING_ENGINE_audience_score_is_deterministic_and_maps_to_channels():
    m = make("AUTONOMOUS_MARKETING_ENGINE", "AutonomousMarketingEngine")
    assert m.score_audience("a") == 97 and m.score_audience("A") == 65 and m.score_audience("") == 0
    assert m.suggest_channels(m.score_audience("a")) == ["social", "video", "influencers"]
    assert m.suggest_channels(65) == ["email", "social"]
    assert m.suggest_channels(70) == ["email", "social"]   # 70 is not above 70
    assert m.suggest_channels(0) == ["email"]


# ── ECONOMIC_INTELLIGENCE_MESH ───────────────────────────────────────────────
def test_ECONOMIC_INTELLIGENCE_MESH_trend_is_mean_step_and_drives_the_risk_label():
    e = make("ECONOMIC_INTELLIGENCE_MESH", "EconomicIntelligenceMesh")
    assert e.summary() == {"count": 0, "trend": 0.0, "risk": "RISK"}   # no data reads as RISK
    e.add_indicator("gdp", 100)
    assert e.trend_score() == 0.0                          # one point is no trend
    e.add_indicator("gdp", 110)
    e.add_indicator("gdp", 120)
    assert e.summary() == {"count": 3, "trend": 10.0, "risk": "OPPORTUNITY"}


def test_ECONOMIC_INTELLIGENCE_MESH_classifies_stable_and_falling_series():
    e = make("ECONOMIC_INTELLIGENCE_MESH", "EconomicIntelligenceMesh")
    e.add_indicator("cpi", 10)
    e.add_indicator("cpi", 12)
    assert e.classify_risk() == "STABLE"                   # +2 per step
    e.add_indicator("cpi", 5)                              # steps +2, -7 -> mean -2.5
    assert e.trend_score() == -2.5 and e.classify_risk() == "RISK"
