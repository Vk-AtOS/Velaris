"""Executive agents that used to be stubs. Web access is stubbed; no network, no real model."""
import socket
import stat

import httpx
import pytest

from velaris.agentkit import biz_common
from velaris.agents.BUSINESS_DNA.main import BusinessDnaAgent
from velaris.agents.BUSINESS_MODEL_ENGINE.main import BUSINESS_MODEL_ENGINEAgent
from velaris.agents.COMPETITIVE_SCANNER.main import COMPETITIVE_SCANNERAgent
from velaris.agents.MARKET_GAP_ANALYZER.main import MARKET_GAP_ANALYZERAgent
from velaris.agents.OPPORTUNITY_RADAR.main import OpportunityRadarAgent
from velaris.agents.STRATEGIC_INTEL.main import StrategicIntelAgent
from velaris.intel.llm import FakeLLM
from velaris.intel.web_fetch import Fetcher


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    for key in biz_common.MODEL_ENV:
        monkeypatch.delenv(key, raising=False)

    def refuse(*args, **kwargs):
        raise AssertionError("test tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    return tmp_path


def site(pages):
    """A Fetcher serving {url: (title, body)} from memory."""
    def handler(request):
        url = str(request.url.copy_with(host=request.headers["host"]))
        if url not in pages:
            return httpx.Response(404)
        title, body = pages[url]
        return httpx.Response(200, headers={"content-type": "text/html"}, text=(
            f"<html><head><title>{title}</title><meta name='description' content='{title} desc'></head>"
            f"<body><article><h1>{title}</h1><p>{body}</p></article></body></html>"))
    return Fetcher(transport=httpx.MockTransport(handler), resolver=lambda host: ["93.184.216.34"],
                   min_gap_s=0, cache_ttl_s=0)


# ---- BUSINESS_DNA ------------------------------------------------------------

def test_business_dna_versions_and_missing_fields(isolated):
    agent = BusinessDnaAgent()
    assert agent.run({"action": "get"})["status"] == "needs_data"
    r = agent.run({"profile": {"name": "Knackforge", "sector": "IT services", "location": "Chennai, Tamil Nadu",
                               "team_size": 25}})
    assert r["profile_version"] == 1 and r["missing_required"] == ["services", "target_customers", "value_proposition"]
    agent.run({"profile": {"services": ["web apps"], "target_customers": "SMEs", "value_proposition": "fast delivery"}})
    got = BusinessDnaAgent().run({"action": "get"})                   # new instance, same file
    assert got["complete"] is True and got["profile_version"] == 2 and got["profile"]["team_size"] == 25
    assert stat.S_IMODE((isolated / "agents" / "BUSINESS_DNA" / "profile.json").stat().st_mode) == 0o600


def test_business_dna_bad_input():
    agent = BusinessDnaAgent()
    assert agent.run({"profile": {"name": ""}})["status"] == "failed"
    assert agent.run({"profile": {"team_size": True, "colour": "red"}})["errors"] == [
        "team_size must be a whole number from 1 to 1000000", "unknown field colour"]
    assert agent.run({"action": "delete"})["status"] == "failed"
    assert agent.run(None)["status"] == "failed"


# ---- BUSINESS_MODEL_ENGINE -----------------------------------------------------

def test_business_model_shares_margin_and_concentration():
    r = BUSINESS_MODEL_ENGINEAgent().analyze([
        {"name": "AMC", "kind": "recurring", "revenue": 600000, "direct_cost": 300000, "customer": "A"},
        {"name": "Portal build", "kind": "project", "revenue": 300000, "direct_cost": 200000, "customer": "B"},
        {"name": "Training", "kind": "one_off", "revenue": 100000, "direct_cost": 0, "customer": "A"}])
    assert (r["total_revenue"], r["gross_profit"], r["gross_margin"], r["recurring_share"]) == \
        ("1000000.00", "500000.00", 0.5, 0.6)
    # customer A 70%, B 30%: HHI 70^2 + 30^2 = 5800
    assert r["customer_concentration"]["hhi"] == 5800.0 and r["customer_concentration"]["top_customer"] == "A"
    assert r["streams"][1]["gross_margin"] == 0.3333


def test_business_model_edges_and_bad_input():
    eng = BUSINESS_MODEL_ENGINEAgent()
    assert eng.analyze([])["status"] == "needs_data"
    assert eng.analyze([{"name": "x", "kind": "project", "revenue": 0}])["status"] == "needs_data"
    no_customers = eng.analyze([{"name": "x", "kind": "project", "revenue": 10}])
    assert no_customers["customer_concentration"] is None
    assert eng.analyze([{"name": "x", "kind": "barter", "revenue": -1}])["status"] == "failed"
    assert eng.analyze("streams")["status"] == "failed"


# ---- COMPETITIVE_SCANNER ---------------------------------------------------------

def test_competitive_scanner_reports_change_and_grounded_extraction(isolated):
    pages = {"https://rival.test/pricing": ("Rival pricing", "Support plans start at Rs 9,999 per month.")}
    fetcher = site(pages)
    agent = COMPETITIVE_SCANNERAgent()
    first = agent.scan([{"name": "Rival", "url": "https://rival.test/pricing"}], fetcher=fetcher)
    assert first["status"] == "ok" and first["results"][0]["changed"] is None
    assert first["results"][0]["title"] == "Rival pricing"
    llm = FakeLLM({"return one JSON object": '{"starting_price": "Rs 9,999 per month", "headcount": 500}'})
    second = COMPETITIVE_SCANNERAgent().scan([{"name": "Rival", "url": "https://rival.test/pricing"}],
                                             fields={"starting_price": "lowest plan price", "headcount": "staff"},
                                             llm=llm, fetcher=fetcher)
    row = second["results"][0]
    assert row["changed"] is False and row["extracted"]["starting_price"] == "Rs 9,999 per month"
    assert row["extracted"]["headcount"] is None and row["ungrounded"] == ["headcount"]   # 500 is not on the page
    pages["https://rival.test/pricing"] = ("Rival pricing", "Support plans now start at Rs 12,000 per month.")
    third = agent.scan([{"name": "Rival", "url": "https://rival.test/pricing"}], fetcher=site(pages))
    assert third["changed"] == ["Rival"]


def test_competitive_scanner_without_data_model_or_page():
    agent = COMPETITIVE_SCANNERAgent()
    assert agent.scan([])["status"] == "needs_data"
    gone = agent.scan([{"name": "Ghost", "url": "https://ghost.test/"}], fields={"price": "price"}, fetcher=site({}))
    assert gone["status"] == "no_results" and gone["results"][0]["status"] == "error"
    no_model = agent.scan([{"name": "R", "url": "https://r.test/"}], fields={"price": "price"},
                          fetcher=site({"https://r.test/": ("R", "Hello there friends")}))
    assert no_model["results"][0]["extraction"] == "not_configured"
    assert agent.scan([{"name": "", "url": "file:///etc/passwd"}])["status"] == "failed"
    assert agent.scan("rival")["status"] == "failed"


# ---- MARKET_GAP_ANALYZER ---------------------------------------------------------

def test_market_gap_classes_and_order():
    r = MARKET_GAP_ANALYZERAgent().analyze(
        needs=[{"need": "Tamil UI", "demand": 12, "source": "survey Q3"}, {"need": "GST invoicing", "demand": 30},
               {"need": "Mobile app", "demand": 20}, {"need": "On-site support", "demand": 5}],
        own_offerings=[{"name": "Billing suite", "covers": ["GST invoicing", "On-site support"]}],
        competitor_offerings=[{"competitor": "Rival", "covers": ["GST invoicing", "Mobile app"]}])
    classes = {n["need"]: n["class"] for n in r["needs"]}
    assert classes == {"gst invoicing": "contested", "mobile app": "competitor_only", "tamil ui": "open_gap",
                       "on-site support": "unique_strength"}
    assert [g["need"] for g in r["gaps"]] == ["mobile app", "tamil ui"]
    assert r["demand_covered_share"] == round(35 / 67, 4)


def test_market_gap_needs_data_and_bad_input():
    eng = MARKET_GAP_ANALYZERAgent()
    assert eng.analyze([])["status"] == "needs_data"
    assert eng.analyze([{"need": "x", "demand": -1}])["status"] == "failed"
    assert eng.analyze([{"need": "x", "demand": 1}, {"need": "X", "demand": 2}])["status"] == "failed"
    assert eng.analyze([{"need": "x", "demand": 1}], own_offerings=[{"name": "a", "covers": "x"}])["status"] == "failed"


# ---- OPPORTUNITY_RADAR -------------------------------------------------------------

def test_opportunity_radar_reports_only_new_results_across_restarts():
    hits = [{"url": "https://tn.test/tender-1", "title": "TN tender for school ERP", "snippet": "Chennai"},
            {"url": "https://tn.test/tender-2", "title": "Hospital software", "snippet": "Madurai"}]
    search = lambda q, limit=8: list(hits)
    first = OpportunityRadarAgent().run({"queries": ["Tamil Nadu ERP tender"], "keywords": ["ERP", "Chennai"]},
                                        search_fn=search)
    assert [r["url"] for r in first["new"]] == ["https://tn.test/tender-1", "https://tn.test/tender-2"]
    assert first["new"][0]["keywords_matched"] == ["ERP", "Chennai"] and first["new"][1]["keywords_matched"] == []
    hits.append({"url": "https://tn.test/tender-3", "title": "New", "snippet": ""})
    second = OpportunityRadarAgent().run({"queries": ["Tamil Nadu ERP tender"]}, search_fn=search)
    assert [r["url"] for r in second["new"]] == ["https://tn.test/tender-3"] and second["seen_before"] == 2


def test_opportunity_radar_no_queries_failures_and_bad_input():
    agent = OpportunityRadarAgent()
    assert agent.run({})["status"] == "needs_data"
    assert agent.run({"queries": ["x"]}, search_fn=lambda q, limit=8: [])["status"] == "no_results"

    def broken(q, limit=8):
        raise OSError("down")
    down = agent.run({"queries": ["x"]}, search_fn=broken)
    assert down["status"] == "no_results" and down["search_errors"] == ["x: OSError"]
    assert agent.run({"queries": [""]})["status"] == "failed"
    assert agent.run({"queries": ["x"], "keywords": "ERP"})["status"] == "failed"


# ---- STRATEGIC_INTEL -----------------------------------------------------------------

def test_strategic_intel_not_configured_and_bad_input():
    agent = StrategicIntelAgent()
    r = agent.run({"question": "Which Tamil Nadu industries are digitising fastest?"})
    assert r["status"] == "not_configured" and r["sources"] == []
    assert agent.run({"question": ""})["status"] == "failed"
    assert agent.run({"question": "q", "max_sources": 0})["status"] == "failed"
    assert agent.run("q")["status"] == "failed"


def test_strategic_intel_cites_only_verified_findings():
    quote = "Tamil Nadu has the largest number of factories in India."
    fetcher = site({"https://stats.test/factories": ("Factories", quote)})
    replies = {"research.plan": '{"sub_questions": ["Tamil Nadu factories"]}',
               "research.learnings": '{"learnings": [{"claim": "%s", "quote": "%s"}]}' % (quote, quote),
               "research.reflect": '{"enough": true, "follow_ups": []}',
               "research.report": "Tamil Nadu leads India in number of factories [1]. It is also the richest state."}
    llm = FakeLLM(lambda prompt, model: replies[llm.calls[-1]["purpose"]])
    r = StrategicIntelAgent().run({"question": "Where are factories in India?", "max_rounds": 1}, llm=llm,
                                  fetcher=fetcher,
                                  search_fn=lambda q, limit=8, f=None: [{"url": "https://stats.test/factories",
                                                                        "title": "", "snippet": ""}])
    assert r["status"] == "ok" and r["learnings"][0]["url"] == "https://stats.test/factories"
    assert "[1]" in r["report"] and "richest" not in r["report"].split("## Sources")[0]
    assert r["unsupported"] == ["It is also the richest state."]
