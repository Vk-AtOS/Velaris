"""Finance agents that used to be stubs: behaviour, with hand-checked numbers. No network."""
import json
import socket
import stat

import httpx
import pytest

from velaris.agentkit import biz_common
from velaris.agents.BANKING_LOGIC_ENGINE.main import AccountProfile, BankingLogicEngine
from velaris.agents.CASHFLOW_AI.main import CashflowAiAgent
from velaris.agents.CLAIMS_ASSESSMENT_ENGINE.main import ClaimCase, ClaimsAssessmentEngine
from velaris.agents.CREDIT_RISK_ENGINE.main import SCORECARD, BorrowerProfile, CreditRiskEngine
from velaris.agents.ECON_INTEL_CORE.main import ECON_INTEL_COREAgent
from velaris.agents.INSURANCE_POLICY_ENGINE.main import InsurancePolicyEngine, PolicyApplication
from velaris.agents.MACRO_ECON_MODEL.main import MacroEconModel, MacroInput
from velaris.agents.NEURAL_ECONOMY.main import NeuralEconomyAgent
from velaris.agents.PRICING_OPTIMIZER.main import PRICING_OPTIMIZERAgent
from velaris.agents.PRICING_OPTIMIZER_ENGINE.main import PricingInput, PricingOptimizerEngine
from velaris.agents.STOCKMARKET_SIGNAL_ENGINE.main import MarketSnapshot, StockMarketSignalEngine
from velaris.intel.llm import FakeLLM, LLMError
from velaris.intel.web_fetch import Fetcher


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Temp data dir, no model configured, and any real network connection fails the test."""
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    for key in biz_common.MODEL_ENV:
        monkeypatch.delenv(key, raising=False)

    def refuse(*args, **kwargs):
        raise AssertionError("test tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    return tmp_path


# ---- BANKING_LOGIC_ENGINE ----------------------------------------------------

def account(**over):
    return AccountProfile(**{"account_id": "acc-1", "account_type": "savings", "balance": 5000.0,
                             "overdraft_limit": 1000.0, "interest_rate": 0.05, "status": "active", **over})


def test_banking_interest_is_simple_actual_365():
    r = BankingLogicEngine().apply_interest(account(), days=30)
    # 5000 x 0.05 x 30 / 365 = 20.5479... -> 20.55
    assert (r["status"], r["interest"], r["new_balance"]) == ("ok", "20.55", "5020.55")
    assert BankingLogicEngine().apply_interest(account(account_id="other"), days=30)["interest"] == "20.55"


def test_banking_overdraft_limit_and_inactive_account():
    eng = BankingLogicEngine()
    assert eng.process_transaction(account(), -5500)["new_balance"] == "-500.00"
    assert eng.process_transaction(account(), -6000.01)["errors"] == ["overdraft limit exceeded"]
    assert eng.process_transaction(account(status="frozen"), 10)["errors"] == ["account not active"]
    assert eng.apply_interest(account(balance=-200.0))["interest"] == "0.00"   # no credit interest on an overdraft


def test_banking_bad_input_fails_without_raising():
    eng = BankingLogicEngine()
    assert eng.apply_interest(account(balance="lots"))["status"] == "failed"
    assert eng.apply_interest(account(account_type=["savings"]))["status"] == "failed"
    assert eng.apply_interest(account(), days=0)["status"] == "failed"
    assert eng.process_transaction(account(), float("nan"))["status"] == "failed"
    assert eng.process_transaction(account(), 0)["errors"] == ["zero amount not allowed"]


# ---- CASHFLOW_AI -------------------------------------------------------------

def test_cashflow_projection_runway_and_weekly_buckets():
    r = CashflowAiAgent().run({
        "opening_balance": 100000, "as_of": "2026-11-01", "horizon_days": 30,
        "receivables": [{"due": "2026-11-11", "amount": 50000}],
        "payables": [{"due": "2026-11-06", "amount": 120000}, {"due": "2026-11-21", "amount": 80000}]})
    assert r["status"] == "ok"
    # 100000 - 120000 = -20000 on the 6th; +50000 = 30000 on the 11th; -80000 = -50000 on the 21st
    assert (r["shortfall_on"], r["runway_days"]) == ("2026-11-06", 5)
    assert (r["lowest_balance"], r["lowest_balance_on"], r["closing_balance"]) == ("-50000.00", "2026-11-21", "-50000.00")
    assert [w["closing_balance"] for w in r["weeks"]][:3] == ["-20000.00", "30000.00", "-50000.00"]
    assert len(r["weeks"]) == 5 and any("due date" in a for a in r["assumptions"])


def test_cashflow_probability_overdue_and_no_shortfall():
    r = CashflowAiAgent().project(1000, as_of="2026-11-10", horizon_days=14, receivables=[
        {"due": "2026-11-12", "amount": 400, "probability": 0.5},      # counts as 200
        {"due": "2026-10-01", "amount": 100},                          # overdue: placed on the as-of date
        {"due": "2027-06-01", "amount": 9999}])                        # beyond the horizon: ignored
    assert (r["closing_balance"], r["overdue_receivables"], r["items_beyond_horizon"]) == ("1300.00", "100.00", 1)
    assert r["runway_days"] is None and r["shortfall_on"] is None


def test_cashflow_bad_input():
    agent = CashflowAiAgent()
    assert agent.run("nonsense")["status"] == "failed"
    r = agent.project("abc", receivables=[{"due": "soon", "amount": -5}], payables="x", horizon_days=0)
    assert r["status"] == "failed" and len(r["errors"]) >= 4
    assert agent.project(0, payables=[{"due": "2026-11-12", "amount": 1, "probability": 0.5}])["status"] == "failed"


# ---- CLAIMS_ASSESSMENT_ENGINE --------------------------------------------------

def claim(**over):
    return ClaimCase(**{"claim_id": "clm-1", "policy_type": "health", "claim_amount": 300000,
                        "incident_severity": 5,
                        "documentation_flags": {"medical_report": True, "bills": True, "id_proof": True},
                        "claimant_history_flags": {}, **over})


def test_claims_payable_and_clean_route():
    r = ClaimsAssessmentEngine().assess(claim(), sum_insured=250000, deductible=10000, copay_pct=10,
                                        auto_settle_limit=250000)
    # min(300000, 250000) - 10000 = 240000; less 10% co-pay = 216000
    assert (r["payable"], r["outcome"], r["deciding_clause"]) == ("216000.00", "eligible_for_settlement", None)
    assert all(c["passed"] for c in r["clauses"]) and r["human_decision_required"] is False


def test_claims_names_the_deciding_clause_and_never_rejects():
    eng = ClaimsAssessmentEngine()
    no_bills = eng.assess(claim(documentation_flags={"medical_report": True, "id_proof": True}), sum_insured=250000)
    assert (no_bills["outcome"], no_bills["deciding_clause"], no_bills["missing_documents"]) == \
        ("pend_for_documents", "C1", ["bills"])
    fraud = eng.assess(claim(claimant_history_flags={"past_fraud": True}), sum_insured=250000, auto_settle_limit=10**7)
    assert (fraud["outcome"], fraud["deciding_clause"]) == ("refer_to_investigator", "C2")
    unknown_cover = eng.assess(claim())
    assert (unknown_cover["outcome"], unknown_cover["deciding_clause"], unknown_cover["payable"]) == \
        ("refer_to_assessor", "C3", None)
    severe = eng.assess(claim(incident_severity=9), sum_insured=500000, auto_settle_limit=10**7)
    assert (severe["outcome"], severe["deciding_clause"]) == ("refer_to_assessor", "C4")
    for r in (no_bills, fraud, unknown_cover, severe):
        assert "reject" not in r["outcome"] and r["human_decision_required"] is True


def test_claims_bad_input():
    eng = ClaimsAssessmentEngine()
    assert eng.assess(claim(), sum_insured=1000, copay_pct=150)["errors"] == ["copay_pct must be between 0 and 100"]
    assert eng.assess(claim(claim_amount=-1))["status"] == "failed"
    assert eng.assess(claim(policy_type={"a": 1}, documentation_flags=None))["status"] == "failed"
    assert eng.assess(claim(), required_docs=[["bills"]])["status"] == "failed"


# ---- CREDIT_RISK_ENGINE --------------------------------------------------------

def test_credit_scorecard_points_are_traceable():
    r = CreditRiskEngine().compute_risk(BorrowerProfile("br-1", 800000, 200000, 12, 1, 500000, "personal"))
    # DTI (200000+500000)/800000 = 0.875 -> 40; 1 delinquency -> 20; 12 years -> 20; LTI 0.625 -> 7
    assert [row["points"] for row in r["breakdown"]] == [40, 20, 20, 7]
    assert (r["score"], r["band"], r["decision"], r["human_decision_required"]) == (87, "low", None, True)
    assert set(r["scorecard"]) == set(SCORECARD) and sum(row["max_points"] for row in r["breakdown"]) == 100


def test_credit_zero_income_and_weak_profile():
    eng = CreditRiskEngine()
    r = eng.compute_risk(BorrowerProfile("br-2", 0, 0, 12, 1, 500000, "home"))
    assert (r["score"], r["band"]) == (40, "high") and r["notes"]       # only delinquency 20 + history 20
    weak = eng.compute_risk(BorrowerProfile("br-3", 100000, 400000, 1, 5, 400000, "auto"))
    assert (weak["score"], weak["band"]) == (0, "high")                 # DTI 8, LTI 4, 5 delinquencies, 1 year


def test_credit_bad_input():
    eng = CreditRiskEngine()
    assert eng.compute_risk(BorrowerProfile("br-4", -1, 0, 1, 0, 1, "personal"))["errors"] == ["income out of range"]
    assert eng.compute_risk(BorrowerProfile("", "a", None, 1, 0, 1, ["x"]))["status"] == "failed"


# ---- INSURANCE_POLICY_ENGINE ---------------------------------------------------

TABLE = {"per_thousand": [{"max_age": 35, "rate": "1.80"}, {"max_age": 60, "rate": "4.50"}],
         "loadings_pct": {"smoker": 25}, "max_income_multiple": 20}


def application(**over):
    return PolicyApplication(**{"policy_id": "pol-1", "applicant_age": 35, "applicant_income": 800000,
                                "sum_assured": 5000000, "policy_type": "term", "tenure_years": 20,
                                "health_flags": {}, **over})


def test_insurance_premium_from_supplied_rate_table():
    eng = InsurancePolicyEngine()
    plain = eng.compute_premium(application(), TABLE)
    assert (plain["annual_premium"], plain["outcome"]) == ("9000.00", "standard_terms")     # 5000 x 1.80
    smoker = eng.compute_premium(application(health_flags={"smoker": True}), TABLE)
    assert (smoker["base_premium"], smoker["annual_premium"]) == ("9000.00", "11250.00")   # +25%
    assert eng.compute_premium(application(applicant_age=36), TABLE)["annual_premium"] == "22500.00"  # 5000 x 4.50
    assert plain["gst"] == "needs_review"


def test_insurance_needs_data_and_referrals():
    eng = InsurancePolicyEngine()
    none = eng.compute_premium(application())
    assert none["status"] == "needs_data" and none["premium"] is None
    cardiac = eng.compute_premium(application(health_flags={"cardiac": True}), TABLE)
    assert (cardiac["outcome"], cardiac["deciding_clause"], cardiac["premium_is_indicative"]) == \
        ("refer_to_underwriter", "U2", True)
    low_income = eng.compute_premium(application(applicant_income=200000), TABLE)       # 20 x 200000 < 5000000
    assert (low_income["outcome"], low_income["deciding_clause"]) == ("refer_to_underwriter", "U1")
    too_old = eng.compute_premium(application(applicant_age=70), TABLE)
    assert too_old["deciding_clause"] == "U3" and too_old["annual_premium"] is None


def test_insurance_bad_input():
    eng = InsurancePolicyEngine()
    assert eng.compute_premium(application(applicant_age=17), TABLE)["errors"] == ["age out of range"]
    assert eng.compute_premium(application(), {"per_thousand": [{"max_age": 35, "rate": "-1"}]})["status"] == "failed"
    assert eng.compute_premium(application(), "table")["status"] == "failed"
    assert eng.compute_premium(application(sum_assured="big", health_flags=[]), TABLE)["status"] == "failed"


# ---- MACRO_ECON_MODEL ----------------------------------------------------------

def test_macro_derived_indicators():
    r = MacroEconModel().compute_index(MacroInput("in", 3500, 5.0, 7.0, 6.5, 5.6, 50),
                                       sources=["https://example.org/release"])
    # misery 5 + 7 = 12; real rate (1.065 / 1.05 - 1) x 100 = 1.4286
    assert (r["misery_index"], r["real_interest_rate_pct"], r["fiscal_stance"]) == (12.0, 1.4286, "deficit")
    assert r["sources"] == ["https://example.org/release"]


def test_macro_no_sources_is_said_and_bad_input_fails():
    model = MacroEconModel()
    r = model.compute_index(MacroInput("in", 3500, 0.0, 0.0, 0.0, -1.0, 50))
    assert (r["misery_index"], r["real_interest_rate_pct"], r["fiscal_stance"]) == (0.0, 0.0, "surplus")
    assert "no sources" in r["data_origin"]
    assert model.compute_index(MacroInput("zz", 1, 1, 1, 1, 1, 1))["errors"] == ["unsupported country"]
    assert model.compute_index(MacroInput(["in"], "x", 1, 1, 1, 1, 1))["status"] == "failed"
    assert model.compute_index(MacroInput("in", 1, 1, 1, 1, 1, 1), sources="web")["status"] == "failed"


# ---- NEURAL_ECONOMY (unit economics) --------------------------------------------

def test_unit_economics_break_even_and_ltv():
    r = NeuralEconomyAgent().run({"price": 1500, "variable_cost": 900, "fixed_costs": 120000, "units": 250,
                                  "arpa": 50000, "gross_margin_pct": 40, "monthly_churn_pct": 2, "cac": 250000})
    # margin 600; 120000 / 600 = 200 units; 250 x 600 - 120000 = 30000; (250 - 200) / 250 = 0.2
    assert (r["contribution_margin"], r["break_even_units"], r["break_even_revenue"]) == ("600.00", 200, "300000.00")
    assert (r["profit_at_units"], r["margin_of_safety"], r["contribution_margin_ratio"]) == ("30000.00", 0.2, 0.4)
    # LTV 50000 x 0.4 / 0.02 = 1000000; LTV:CAC 4; payback 250000 / 20000 = 12.5 months
    assert (r["ltv"], r["ltv_to_cac"], r["cac_payback_months"]) == ("1000000.00", 4.0, 12.5)


def test_unit_economics_edges_and_bad_input():
    agent = NeuralEconomyAgent()
    below_cost = agent.run({"price": 100, "variable_cost": 100, "fixed_costs": 10})
    assert below_cost["break_even_units"] is None and "no volume" in below_cost["note"]
    assert agent.run({"price": 10, "variable_cost": 4, "fixed_costs": 25})["break_even_units"] == 5    # 4.17 -> 5
    assert agent.run({})["status"] == "needs_data"
    assert agent.run({"price": 10, "variable_cost": 4, "fixed_costs": -1})["status"] == "failed"
    assert agent.run({"arpa": 100, "gross_margin_pct": 40, "monthly_churn_pct": 0})["status"] == "failed"
    assert agent.run([1, 2])["status"] == "failed"


# ---- PRICING_OPTIMIZER_ENGINE / PRICING_OPTIMIZER -------------------------------

POINTS = [(100, 500), (120, 400), (140, 300), (160, 200)]       # exactly q = 1000 - 5p


def test_pricing_fit_then_maximise_margin():
    r = PricingOptimizerEngine().optimize_from_demand("svc", 60, POINTS)
    # p* = 60/2 + 1000/10 = 130; q = 350; profit = 70 x 350 = 24500
    assert (r["optimal_price"], r["expected_quantity"], r["expected_profit"]) == (130.0, 350.0, 24500.0)
    assert (r["fit"]["slope"], r["fit"]["intercept"], r["fit"]["r_squared"], r["bound_applied"]) == (-5.0, 1000.0, 1.0, None)
    capped = PricingOptimizerEngine().optimize_from_demand("svc", 60, POINTS, max_price=120)
    assert (capped["optimal_price"], capped["expected_profit"], capped["bound_applied"]) == (120.0, 24000.0, "max_price")


def test_pricing_refuses_with_too_little_or_perverse_data():
    eng = PricingOptimizerEngine()
    few = eng.optimize_from_demand("svc", 60, [(100, 500), (100, 480), (120, 400)])
    assert few["status"] == "needs_data" and few["optimal_price"] is None and "2 distinct" in few["reason"]
    rising = eng.optimize_from_demand("svc", 60, [(100, 200), (120, 300), (140, 400)])
    assert rising["status"] == "needs_data" and rising["fit"]["slope"] == 5.0
    assert eng.optimize_from_demand("svc", 60, [(100, 500), "x", (0, 1)])["status"] == "failed"
    assert eng.optimize_from_demand("svc", 60, POINTS, min_price=200, max_price=100)["status"] == "failed"


def test_pricing_elasticity_rule_and_delegate():
    eng = PricingOptimizerEngine()
    r = eng.optimize(PricingInput("svc", 100, 50, 50, 1, 2.0, {"premium_positioning": True}))
    assert r["optimal_price"] == 200.0 and "premium_positioning" in r["ignored_inputs"]     # 100 x 2 / (2 - 1)
    inelastic = eng.optimize(PricingInput("svc", 100, 50, 50, 1, 0.8, {}))
    assert inelastic["status"] == "needs_data"
    assert eng.optimize(PricingInput("svc", 100, 50, 50, 1, 0.8, {}), max_price=150)["optimal_price"] == 150
    assert eng.optimize(PricingInput("svc", -1, 50, 50, 1, 2.0, {}))["errors"] == ["base_cost invalid"]
    front = PRICING_OPTIMIZERAgent()
    assert front.optimize({"product_id": "svc", "unit_cost": 60, "points": POINTS}) == \
        eng.optimize_from_demand("svc", 60, POINTS)
    assert front.optimize({"product_id": "svc", "unit_cost": 100, "elasticity": 2})["optimal_price"] == 200.0
    assert front.optimize({"product_id": "svc"})["status"] == "needs_data"
    assert front.optimize(None)["status"] == "failed"
    assert front.optimize({"elasticity": "high"})["status"] == "failed"


# ---- STOCKMARKET_SIGNAL_ENGINE --------------------------------------------------

def test_stock_indicators_on_a_steady_rise():
    prices = [float(p) for p in range(1, 31)]
    r = StockMarketSignalEngine().compute_signal(MarketSnapshot("ACME", prices, [100] * 29 + [300], "tech"))
    ind = r["indicators"]
    # last five 26..30 -> 28; last twenty 11..30 -> 20.5; 30/20 - 1 = 50%; every change is a gain -> RSI 100
    assert (ind["sma_5"], ind["sma_20"], ind["roc_10_pct"], ind["rsi_14"], ind["volume_ratio"]) == (28.0, 20.5, 50.0, 100.0, 3.0)
    assert ind["macd"] is not None and ind["macd_signal"] is None and "macd_signal" in r["not_computed"]
    assert r["signal"] is None and r["kind"] == "indicators" and "Not investment advice" in r["disclaimer"]


def test_stock_rsi_is_50_when_gains_equal_losses_and_short_series():
    alternating = [10, 11] * 7 + [10]              # 7 gains of 1, 7 losses of 1
    r = StockMarketSignalEngine().compute_signal(MarketSnapshot("X", alternating, [1] * 15, "tech"))
    assert r["indicators"]["rsi_14"] == 50.0 and r["indicators"]["sma_20"] is None
    short = StockMarketSignalEngine().compute_signal(MarketSnapshot("X", [1, 2, 3, 4, 5], [1] * 5, "tech"))
    assert short["indicators"]["sma_5"] == 3.0 and short["indicators"]["rsi_14"] is None


def test_stock_bad_input():
    eng = StockMarketSignalEngine()
    assert eng.compute_signal(MarketSnapshot("X", [1, 2, -3, 4, 5], [1] * 5, "tech"))["status"] == "failed"
    assert eng.compute_signal(MarketSnapshot("X", [1, 2], [1, 2], "tech"))["status"] == "failed"
    assert eng.compute_signal(MarketSnapshot("X", "prices", None, {}))["status"] == "failed"
    assert eng.compute_signal(MarketSnapshot("X", [1, 2, "3", 4, 5], [1] * 5, "tech"))["status"] == "failed"


# ---- ECON_INTEL_CORE -----------------------------------------------------------

def test_econ_register_requires_a_source_and_survives_restart(isolated):
    agent = ECON_INTEL_COREAgent()
    assert agent.record_indicator("CPI inflation", "2026-09", 4.2, "")["status"] == "failed"
    assert agent.record_indicator("CPI inflation", "Sept", "4", "ftp://x")["status"] == "failed"
    assert agent.summary("CPI inflation")["status"] == "needs_data"
    src = "https://example.org/cpi"
    assert agent.record_indicator("CPI inflation", "2026-08", 4.0, src, "%")["status"] == "ok"
    assert agent.record_indicator("CPI inflation", "2026-09", 4.5, src, "%")["replaced"] is False
    s = ECON_INTEL_COREAgent().summary("cpi inflation")              # a new instance reads the same file
    assert (s["latest"]["period"], s["change"], s["change_pct"], s["sources"]) == ("2026-09", 0.5, 12.5, [src])
    path = isolated / "agents" / "ECON_INTEL_CORE" / "indicators.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_econ_research_not_configured_and_with_a_scripted_model():
    agent = ECON_INTEL_COREAgent()
    assert agent.research("What is the repo rate?")["status"] == "not_configured"
    assert agent.research("")["status"] == "failed"
    quote = "The policy repo rate was kept unchanged at 6.50 per cent."

    def handler(request):
        return httpx.Response(200, headers={"content-type": "text/html"}, text=(
            f"<html><head><title>Policy</title></head><body><article><h1>Policy</h1><p>{quote}</p>"
            "</article></body></html>"))
    fetcher = Fetcher(transport=httpx.MockTransport(handler), resolver=lambda host: ["93.184.216.34"],
                      min_gap_s=0, cache_ttl_s=0)
    replies = {"plan": json.dumps({"sub_questions": ["policy repo rate"]}),
               "learnings": json.dumps({"learnings": [{"claim": "The repo rate is 6.50%.", "quote": quote}]}),
               "reflect": json.dumps({"enough": True, "follow_ups": []}),
               "report": "The repo rate is 6.50 per cent [1]."}

    def script(prompt, model):
        purpose = llm.calls[-1]["purpose"].removeprefix("research.")
        if purpose not in replies:
            raise LLMError(purpose)
        return replies[purpose]
    llm = FakeLLM(script)
    r = agent.research("What is the repo rate?", llm=llm, fetcher=fetcher,
                       search_fn=lambda q, limit=8, f=None: [{"url": "https://bank.test/policy", "title": "", "snippet": ""}])
    assert r["status"] == "ok" and r["learnings"][0]["quote"] == quote
    assert r["sources"][0]["url"] == "https://bank.test/policy" and "[1]" in r["report"]
    empty = agent.research("What is the repo rate?", llm=llm, fetcher=fetcher, search_fn=lambda q, limit=8, f=None: [])
    assert empty["status"] == "no_findings" and empty["learnings"] == []
