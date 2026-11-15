"""KAN-94: sales and marketing agent defects."""
import asyncio
import sqlite3
from datetime import datetime
from importlib import import_module

import pytest


def mod(name):
    return import_module(f"velaris.agents.{name}.main")


def test_whatsapp_logs_local_time_so_the_local_date_filter_matches(monkeypatch):
    M = mod("WHATSAPP_BRIEFING")

    class IndiaEarlyMorning(datetime):                         # 00:30 IST on the 15th is still the 14th in UTC
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 15, 0, 30)

        @classmethod
        def utcnow(cls):
            return cls(2026, 11, 14, 19, 0)
    monkeypatch.setattr(M, "datetime", IndiaEarlyMorning)
    a = M.WhatsAppBriefingAgent()
    a.log_metric("Calls", 3)
    assert a.get_briefing_dict()["metrics"] == [{"name": "Calls", "value": 3.0, "unit": ""}]
    a.system.db.execute("UPDATE daily_metrics SET timestamp='2000-01-01T00:00:00'")      # not today's
    assert a.get_briefing_dict()["metrics"] == []


def test_whatsapp_send_briefing_works_inside_a_running_loop():
    a = mod("WHATSAPP_BRIEFING").WhatsAppBriefingAgent()

    async def inside():
        return a.send_briefing()
    assert asyncio.run(inside())["status"] == "preview"       # was RuntimeError: asyncio.run() in a running loop
    assert a.send_briefing()["status"] == "preview"


def test_sales_navigator_validates_ratings_and_is_honest_about_probability():
    n = mod("AUTONOMOUS_SALES_NAVIGATOR").AutonomousSalesNavigator()
    lead = n.add_lead("Acme", 80, 60, 50)
    assert n.score_lead(lead) == 65 and n.predict_close_probability(lead) == 0.65
    for bad in ((1000, 1, 1), (-5, 1, 1), (float("nan"), 1, 1), ("9", 1, 1), (True, 1, 1)):
        with pytest.raises(ValueError):
            n.add_lead("x", *bad)
    with pytest.raises(ValueError):
        n.add_lead("", 1, 1, 1)
    assert "NOT a probability" in type(n).__doc__
    assert [l["name"] for l in n.top_leads(1)] == ["Acme"]


def test_domain_advisor_slow_cycle_rule_runs_when_the_company_median_is_zero():
    deals = [{"vertical": "A", "status": "won", "amount": 10, "opened": "2026-01-01", "closed": "2026-01-01"}] * 6 + \
            [{"vertical": "B", "status": "won", "amount": 10, "opened": "2026-01-01", "closed": "2026-01-20"}] * 3 + \
            [{"vertical": "C", "status": "won", "amount": 10, "opened": "2026-01-01", "closed": "2026-01-01"}] * 8
    r = mod("DOMAIN_ADVISOR").DOMAIN_ADVISORAgent().advise(deals, min_closed=3)
    assert {(a["rule"], a["vertical"]) for a in r["advice"] if a["rule"] == "A5"} == {("A5", "b")}


def test_vmrk_verify_never_raises_on_odd_input():
    v = mod("VMRK").VMRK()
    sig = v.sign("hello")
    assert v.verify("hello", sig) is True
    for bad in ("é" * 5, "‮", 5, None, ""):
        assert v.verify("hello", bad) is False


def test_marketing_score_needs_measured_data():
    m = mod("AUTONOMOUS_MARKETING_ENGINE").AutonomousMarketingEngine()
    with pytest.raises(ValueError):
        m.score_audience("young professionals")               # a name is not a measurement
    assert m.score_audience({"size": 1_000_000, "engagement": 1, "conversion": 1}) == 100
    assert m.score_audience({"size": 0, "engagement": 0, "conversion": 0}) == 0
    assert m.score_audience({"size": 1000, "engagement": 0.5, "conversion": 0.1}) \
        > m.score_audience({"size": 1000, "engagement": 0.1, "conversion": 0.1})
    for bad in ({"size": -1, "engagement": 0, "conversion": 0}, {"size": 5, "engagement": 2, "conversion": 0},
                {"size": float("nan"), "engagement": 0, "conversion": 0}):
        with pytest.raises(ValueError):
            m.score_audience(bad)
    with pytest.raises(ValueError):
        m.generate_campaign("p", "a", -5)


def test_funnel_rejects_impossible_counts_and_suggests_optimisations():
    f = mod("BUSINESS_FUNNEL_DESIGNER").BusinessFunnelDesigner()
    f.create_funnel("web", ["visit", "signup", "pay"])
    assert f.record_stage("web", "visit", 100, 40) and f.record_stage("web", "signup", 40, 10)
    assert f.record_stage("web", "pay", 10, 1)
    for bad in ((-1, 0), (10, -1), (1.5, 1), (True, 0), (float("nan"), 0)):
        assert f.record_stage("web", "visit", *bad) is False
    assert f.record_stage("web", "visit", 0, 61) is False      # the running total may not exceed visits either
    tips = f.suggest_optimizations("web", threshold=70)
    assert [t["stage"] for t in tips] == ["pay", "signup"] or [t["stage"] for t in tips] == ["signup", "pay"]
    assert tips[0]["drop_off"] >= tips[-1]["drop_off"] and f.suggest_optimizations("nope") == []
    with pytest.raises(ValueError):
        f.create_funnel("bad", ["a", "a"])
