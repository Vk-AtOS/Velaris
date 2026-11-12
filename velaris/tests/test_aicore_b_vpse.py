"""VPSE family: trend fit and forecast, what-if scenarios over formulas, and the projection that joins them."""
import pytest

from velaris.agents.VPSE_CORE.main import VPSE_COREAgent
from velaris.agents.VPSE_MODELER.main import VPSE_MODELERAgent
from velaris.agents.VPSE_SCENARIO.main import VPSE_SCENARIOAgent


def test_modeler_recovers_an_exact_line():
    m = VPSE_MODELERAgent()
    fit = m.fit([10, 12, 14, 16, 18])
    assert fit["slope"] == 2.0 and fit["intercept"] == 10.0 and fit["r2"] == 1.0 and fit["residual_sd"] == 0.0
    f = m.forecast([10, 12, 14, 16, 18], horizon=2)["forecast"]
    assert [p["value"] for p in f] == [20.0, 22.0] and f[0]["low"] == f[0]["high"] == 20.0


def test_modeler_noisy_series_has_a_band_and_flat_series_is_flat():
    m = VPSE_MODELERAgent()
    noisy = m.forecast([100, 108, 97, 115, 104, 121], horizon=1)
    point = noisy["forecast"][0]
    assert 0 < noisy["model"]["r2"] < 1 and point["low"] < point["value"] < point["high"]
    flat = m.fit([5, 5, 5, 5])
    assert flat["slope"] == 0.0 and flat["r2"] == 1.0


@pytest.mark.parametrize("series, horizon", [([1, 2], 1), ("12345", 1), ([1, 2, "3"], 1), ([1, 2, 3], 0),
                                             ([1, 2, 3], 500), ([1, 2, float("nan")], 1), (None, 1)])
def test_modeler_bad_input(series, horizon):
    r = VPSE_MODELERAgent().forecast(series, horizon)
    assert r["status"] == "invalid_input" and r["forecast"] == []


BASE = {"price": 100, "units": 50, "fixed_cost": 3000}
FORMULAS = {"profit": "revenue - fixed_cost", "revenue": "price * units", "margin": "profit / revenue * 100"}


def test_scenario_recomputes_chained_formulas():
    r = VPSE_SCENARIOAgent().run(BASE, FORMULAS, [
        {"name": "price cut", "changes": {"price": {"pct": -10}, "units": {"pct": 20}}},
        {"name": "rent up", "changes": {"fixed_cost": {"add": 500}}},
        {"name": "floor", "changes": {"units": {"set": 0}}},
    ])
    assert r["base"] == {"profit": 2000.0, "revenue": 5000.0, "margin": 40.0}
    assert r["evaluation_order"] == ["revenue", "profit", "margin"]
    cut, rent, floor = r["scenarios"]
    assert cut["outcomes"]["revenue"] == 5400.0 and cut["delta"]["profit"] == 400.0 and cut["delta_pct"]["profit"] == 20.0
    assert rent["outcomes"]["profit"] == 1500.0 and rent["delta"]["revenue"] == 0.0
    assert floor["status"] == "error" and "division" in floor["reason"] and floor["outcomes"] is None


def test_scenario_base_only_and_functions():
    r = VPSE_SCENARIOAgent().run({"a": 3, "b": -7}, {"x": "max(a, abs(b)) + round(a / 2)", "y": "-a ** 2"})
    assert r["base"] == {"x": 9.0, "y": -9.0} and r["scenarios"] == []


@pytest.mark.parametrize("formulas, scenarios, fragment", [
    ({"x": "__import__('os').system('true')"}, None, "other than arithmetic"),
    ({"x": "price.real"}, None, "other than arithmetic"),
    ({"x": "price +"}, None, "cannot parse"),
    ({"x": "nonexistent * 2"}, None, "unknown name"),
    ({"x": "y + 1", "y": "x + 1"}, None, "circle"),
    ({"x": "price / (units - 50)"}, None, "arithmetic failed"),
    ({"x": "price ** 99"}, None, "exponents"),
    ({"price": "units * 2"}, None, "both drivers and outcomes"),
    ({"x": "price"}, [{"name": "s", "changes": {"ghost": {"pct": 1}}}], "unknown driver"),
    ({"x": "price"}, [{"name": "s", "changes": {"price": {"times": 2}}}], "must be one of"),
    ({"x": "price"}, [{"changes": {}}], "needs a 'name'"),
])
def test_scenario_rejects_unsafe_or_broken_input(formulas, scenarios, fragment):
    r = VPSE_SCENARIOAgent().run(BASE, formulas, scenarios)
    assert r["status"] == "invalid_input" and fragment in r["reason"]


def test_scenario_bad_base():
    s = VPSE_SCENARIOAgent()
    assert s.run({"price": "100"}, {"x": "price"})["status"] == "invalid_input"
    assert s.run({}, {"x": "1"})["status"] == "invalid_input"
    assert s.run(BASE, {})["status"] == "invalid_input"


def test_core_projects_each_period_under_each_scenario():
    r = VPSE_COREAgent().project(
        [100, 110, 120, 130], horizon=2, driver="units", constants={"price": 10},
        formulas={"revenue": "price * units"},
        scenarios=[{"name": "discount", "changes": {"price": {"pct": -20}}}])
    assert [p["units"] for p in r["periods"]] == [140.0, 150.0]
    assert r["periods"][0]["cases"] == {"base": {"revenue": 1400.0}, "discount": {"revenue": 1120.0}}
    assert r["totals"] == {"base": {"revenue": 2900.0}, "discount": {"revenue": 2320.0}}
    assert r["model"]["slope"] == 10.0


def test_core_defaults_and_bad_input():
    core = VPSE_COREAgent()
    plain = core.project([1, 2, 3], horizon=1)
    assert plain["periods"][0]["cases"] == {"base": {"projected": 4.0}}
    assert core.project([1, 2], horizon=1)["status"] == "invalid_input"
    assert core.project([1, 2, 3], formulas={"x": "import os"})["status"] == "invalid_input"
    assert core.project([1, 2, 3], scenarios=[{"name": "base", "changes": {}}])["status"] == "invalid_input"
    assert core.project([1, 2, 3], constants="none")["periods"] == []
