"""KAN-85 finance and KAN-70 supply chain / client success remainders."""
from importlib import import_module

import pytest


def agent(name, marker, *args):
    m = import_module(f"velaris.agents.{name}.main")
    cls = next(v for v in vars(m).values() if isinstance(v, type) and hasattr(v, marker) and v.__module__ == m.__name__)
    return cls(*args), m


def test_growth_from_a_zero_or_negative_base_is_undefined_not_zero():
    f, _ = agent("FINANCIAL_AI_ENGINE", "compute_growth")
    assert f.compute_growth(100, 150) == 50.0
    assert f.compute_growth(0, 10) is None and f.compute_growth(-5, 10) is None


def test_demand_projection_never_goes_negative():
    e, _ = agent("ECONOVA", "demand_projection")
    assert e.demand_projection(100, 10) == 0.0 and e.demand_projection(100, 0) == 100


def test_flat_trend_is_stable_and_indicators_are_not_mixed():
    m, _ = agent("ECONOMIC_INTELLIGENCE_MESH", "classify_risk")
    m.add_indicator("cpi", 5.0)
    m.add_indicator("cpi", 5.0)
    assert m.trend_score() == 0.0 and m.classify_risk() == "STABLE"          # flat is not a RISK
    m2, _ = agent("ECONOMIC_INTELLIGENCE_MESH", "classify_risk")
    for name, v in (("cpi", 5.0), ("gdp", 100.0), ("cpi", 5.0), ("gdp", 100.0)):
        m2.add_indicator(name, v)
    assert m2.trend_score() == 0.0                                           # was (95 - 95 + 95) / 3: a CPI-to-GDP "change"
    m3, _ = agent("ECONOMIC_INTELLIGENCE_MESH", "classify_risk")
    m3.add_indicator("cpi", 5.0)
    m3.add_indicator("cpi", 4.0)
    assert m3.classify_risk() == "RISK"


def test_supply_chain_zero_lead_time_orders_are_reported_as_received():
    from velaris.agents.SUPPLY_CHAIN_ENGINE import main as M
    eng = M.SupplyChainEngine() if hasattr(M, "SupplyChainEngine") else agent("SUPPLY_CHAIN_ENGINE", "compute_plan")[0]
    sc = M.SupplyChainInput(chain_id="c", demand_forecast=[10, 10, 10], lead_time_days=0, safety_stock=0,
                            holding_cost=1, shortage_cost=1, max_capacity=15)
    plan = eng.compute_plan(sc, opening_stock=5)
    total_received = sum(r["received"] for r in plan["schedule"])
    assert total_received == sum(o["quantity"] for o in plan["orders"]) > 0
    over = eng.compute_plan(sc, opening_stock=16)
    assert over["status"] != "ok"                                            # opening stock above capacity


def test_machine_install_year_must_be_whole():
    from velaris.agents.MACHINE_LIFECYCLE_ENGINE import main as M
    eng = agent("MACHINE_LIFECYCLE_ENGINE", "validate")[0]
    m = M.MachineLifecycleInput("m1", 2020.5, 100.0, {}, {}, 1.0)
    assert any("whole" in e for e in eng.validate(m, 2026))
    assert eng.validate(M.MachineLifecycleInput("m1", 2020, 100.0, {}, {}, 1.0), 2026) == []


def test_logista_validates_and_never_picks_nan():
    lg, _ = agent("LOGISTA", "choose_route")
    assert lg.allocate_resources({"a": 5}, {"a": 8, "b": 1}) == {"a": 5, "b": 0}
    for bad in ({"a": -1}, {"a": "x"}, {"a": float("nan")}):
        with pytest.raises(ValueError):
            lg.allocate_resources({"a": 5}, bad)
    assert lg.choose_route({"x": float("nan"), "y": 3.0, "z": 5.0}) == "y"
    assert lg.choose_route({"x": float("nan")}) is None and lg.choose_route({}) is None
