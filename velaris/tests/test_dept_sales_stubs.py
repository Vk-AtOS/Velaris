"""Sales DOMAIN_* agents (a "domain" is a sales vertical). Search is stubbed; no network."""
import socket

import pytest

from velaris.agents.DOMAIN_ADVISOR.main import DOMAIN_ADVISORAgent
from velaris.agents.DOMAIN_EXPANSION.main import DOMAIN_EXPANSIONAgent
from velaris.agents.DOMAIN_MASTERY.main import DOMAIN_MASTERYAgent
from velaris.agents.DOMAIN_REFINER.main import DOMAIN_REFINERAgent
from velaris.agents.DOMAIN_SCOUT.main import DOMAIN_SCOUTAgent


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))

    def refuse(*args, **kwargs):
        raise AssertionError("test tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)


def deal(vertical, status, amount, opened=None, closed=None):
    return {"vertical": vertical, "status": status, "amount": amount, "opened": opened, "closed": closed}


# healthcare: 4 won of 5 closed, 30-day cycles; textiles: 1 won of 5 closed, 90-day cycle; logistics: 1 closed
DEALS = ([deal("Healthcare", "won", 200000, "2026-01-01", "2026-01-31") for _ in range(4)]
         + [deal("healthcare ", "lost", 100000)]
         + [deal("Textiles", "won", 100000, "2026-01-01", "2026-04-01")]
         + [deal("Textiles", "lost", 50000) for _ in range(4)]
         + [deal("Logistics", "won", 50000), deal("Logistics", "open", 70000)])


def test_mastery_per_vertical_by_hand():
    r = DOMAIN_MASTERYAgent().assess(DEALS)
    rows = {v["vertical"]: v for v in r["verticals"]}
    assert [v["vertical"] for v in r["verticals"]] == ["healthcare", "textiles", "logistics"]   # by won revenue
    h = rows["healthcare"]
    assert (h["won"], h["lost"], h["win_rate"], h["won_revenue"], h["avg_won_deal"]) == (4, 1, 0.8, "800000.00", "200000.00")
    assert (h["revenue_share"], h["median_cycle_days"], h["established"]) == (round(800000 / 950000, 4), 30, True)
    assert rows["textiles"]["win_rate"] == 0.2 and rows["logistics"]["sample_too_small"] is True
    assert rows["logistics"]["open"] == 1 and r["established"] == ["healthcare", "textiles"]


def test_mastery_empty_and_bad_input():
    agent = DOMAIN_MASTERYAgent()
    assert agent.assess([])["status"] == "needs_data"
    assert agent.assess([deal("x", "maybe", 1)])["status"] == "failed"
    assert agent.assess([deal("x", "won", -1)])["status"] == "failed"
    assert agent.assess([deal("x", "won", 1, "2026-02-01", "2026-01-01")])["status"] == "failed"
    assert agent.assess(DEALS, min_closed=0)["status"] == "failed"
    assert agent.assess("deals")["status"] == "failed"


def test_advisor_rules_with_evidence():
    r = DOMAIN_ADVISORAgent().advise(DEALS)
    # company: 6 won of 11 closed = 54.5%; median won cycle of [30,30,30,30,90] = 30
    got = {(a["vertical"], a["rule"]) for a in r["advice"]}
    assert got == {("healthcare", "A2"), ("healthcare", "A4"), ("textiles", "A3"), ("textiles", "A5"),
                   ("logistics", "A1")}
    a3 = next(a for a in r["advice"] if a["rule"] == "A3")
    assert a3["evidence"] == "win rate 20% vs company 55% over 5 closed"
    assert r["company"] == {"win_rate": 0.5455, "median_cycle_days": 30, "closed_deals": 11}


def test_advisor_empty_and_bad_input():
    assert DOMAIN_ADVISORAgent().advise([])["status"] == "needs_data"
    assert DOMAIN_ADVISORAgent().advise([{"vertical": ""}])["status"] == "failed"
    few = DOMAIN_ADVISORAgent().advise([deal("x", "won", 10)])
    assert [a["rule"] for a in few["advice"]] == ["A1"]


def test_expansion_needs_sourced_market_sizes():
    agent = DOMAIN_EXPANSIONAgent()
    assert agent.assess(DEALS)["status"] == "needs_data"
    assert agent.assess(DEALS, {"healthcare": {"size": 1000000}})["status"] == "failed"       # no source
    r = agent.assess(DEALS, {"Healthcare": {"size": 10000000, "source": "industry report p.4"},
                             "Education": {"size": 2000000, "source": "survey"}})
    assert [v["vertical"] for v in r["verticals"]] == ["healthcare", "education"]
    h, e = r["verticals"]
    assert (h["penetration"], h["whitespace"], h["entered"]) == (0.08, "9200000.00", True)
    assert (e["penetration"], e["whitespace"], e["entered"]) == (0.0, "2000000.00", False)
    assert r["verticals_without_market_size"] == ["logistics", "textiles"]
    assert agent.assess(DEALS, [1, 2])["status"] == "failed"


def test_refiner_maps_exact_alias_and_only_suggests_close_spellings():
    r = DOMAIN_REFINERAgent().refine(
        ["Health care", "healthcare", " HEALTHCARE ", "Hospitals", "Texttiles", "Space mining"],
        ["Healthcare", "Textiles"], aliases={"hospitals": "Healthcare"})
    assert r["mapping"] == {"healthcare": "Healthcare", " HEALTHCARE ": "Healthcare", "Hospitals": "Healthcare"}
    assert [(s["label"], s["suggestion"]) for s in r["suggestions"]] == [("Health care", "Healthcare"),
                                                                         ("Texttiles", "Textiles")]
    assert r["unmapped"] == ["Space mining"] and "Texttiles" not in r["mapping"]
    assert r["counts"] == {"exact": 2, "alias": 1, "suggested": 2, "unmapped": 1}


def test_refiner_bad_input():
    agent = DOMAIN_REFINERAgent()
    assert agent.refine(["x"], [])["status"] == "needs_data"
    assert agent.refine(["x"], ["A"], aliases={"y": "B"})["status"] == "failed"
    assert agent.refine(["x"], ["A"], aliases="y")["status"] == "failed"
    assert agent.refine("x", ["A"], cutoff=2)["status"] == "failed"


def test_scout_returns_sources_with_the_query_that_found_them():
    seen = []

    def search(q, limit=8):
        seen.append(q)
        return [{"url": "https://assoc.test/members", "title": "Textile association", "snippet": "Tiruppur"},
                {"url": "javascript:alert(1)", "title": "bad", "snippet": ""}]
    r = DOMAIN_SCOUTAgent().scout("Textiles", "Tamil Nadu", search_fn=search)
    assert seen[0] == "Textiles industry Tamil Nadu companies" and len(seen) == 3
    assert r["status"] == "ok" and [x["url"] for x in r["results"]] == ["https://assoc.test/members"]
    assert r["results"][0]["found_by"] == seen


def test_scout_no_vertical_and_bad_input():
    agent = DOMAIN_SCOUTAgent()
    assert agent.scout("")["status"] == "needs_data"
    assert agent.scout(["Textiles"])["status"] == "failed"
    assert agent.scout("x", search_fn=lambda q, limit=8: [])["status"] == "no_results"
