"""Round 3 (KAN-94, KAN-85, KAN-88): FAILPATH bounds, PORTFOLIO_SIM symmetry, AGENT_CONTAINMENT_MODES tests."""
import pytest

from velaris.agents.AGENT_CONTAINMENT_MODES.main import AgentContainmentModes
from velaris.agents.FAILPATH_CONTROL_ENGINE.main import FailpathControlEngine
from velaris.agents.PORTFOLIO_SIM_ENGINE.main import PortfolioInput, PortfolioSimEngine
from velaris.core.access import SECURITY_ADMIN, Caller, acting_as
from velaris.intel import trace

SEC = Caller("sec", "kf", frozenset({SECURITY_ADMIN}))
BOB = Caller("bob", "kf", frozenset())


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_failpath_validates_bounds_history_and_copies_context(monkeypatch):
    import velaris.agents.FAILPATH_CONTROL_ENGINE.main as m
    monkeypatch.setattr(m, "MAX_HISTORY", 3)
    f = FailpathControlEngine()
    assert f.register_handler("E1", "safe_stop") and not f.register_handler("E1", "x")
    ctx = {"a": 1}
    r = f.route_failure("E1", ctx)
    ctx["a"] = 2
    r["context"]["a"] = 3
    assert f.list_history()[0]["context"] == {"a": 1} and r["handler"] == "safe_stop"
    for i in range(5):
        f.route_failure("E2", {"i": i})
    assert [h["context"]["i"] for h in f.list_history()] == [2, 3, 4] and f.get_handler("E2") == "UNHANDLED"
    for call in (lambda: f.register_handler("", "x"), lambda: f.register_handler("c", None),
                 lambda: f.route_failure(None, {}), lambda: f.route_failure("E1", "not a dict"),
                 lambda: f.register_handler("x" * 201, "a")):
        with pytest.raises(ValueError):
            call()


def pf(**kw):
    base = dict(portfolio_id="p", assets={"A": 0.5, "B": 0.5}, expected_returns={"A": 0.1, "B": 0.08},
                volatilities={"A": 0.2, "B": 0.1}, correlations={"A": {"A": 1, "B": 0.3}, "B": {"A": 0.3, "B": 1}})
    base.update(kw)
    return PortfolioInput(**base)


def test_portfolio_correlations_must_be_symmetric_complete_and_unit_diagonal():
    e = PortfolioSimEngine()
    assert e.simulate(pf())["status"] == "ok"
    asym = e.simulate(pf(correlations={"A": {"A": 1, "B": 0.9}, "B": {"A": -0.5, "B": 1}}))
    assert asym["status"] == "failed" and any("not symmetric" in x for x in asym["errors"])
    diag = e.simulate(pf(correlations={"A": {"A": 0.2, "B": 0.3}, "B": {"A": 0.3, "B": 1}}))
    assert any("must be 1" in x for x in diag["errors"])
    gap = e.simulate(pf(correlations={"A": {"A": 1}, "B": {"A": 0.3, "B": 1}}))              # used to raise KeyError
    assert gap["status"] == "failed" and any("missing correlation A-B" in x for x in gap["errors"])


@pytest.mark.parametrize("field, value", [("assets", {"A": float("nan"), "B": 0.5}), ("expected_returns", {"A": "x", "B": 0.1}),
                                          ("volatilities", {"A": True, "B": 0.1}), ("assets", None)])
def test_portfolio_refuses_values_that_are_not_finite_numbers(field, value):
    assert PortfolioSimEngine().simulate(pf(**{field: value}))["status"] == "failed"


def test_containment_only_a_security_admin_sets_modes_and_unset_allows_nothing():
    c = AgentContainmentModes()
    assert c.get_mode("A1") == "UNSET" and c.allowed_actions("A1") == []                   # an unknown agent is not trusted
    assert c.set_mode("A1", "SANDBOX") is False                                            # no caller
    with acting_as(BOB):
        assert c.set_mode("A1", "SANDBOX") is False and c.set_metadata("A1", {"x": 1}) is False
    assert c.get_mode("A1") == "UNSET"
    with acting_as(SEC):
        assert c.set_mode("A1", "SANDBOX") and c.allowed_actions("A1") == ["read", "compute"]
        assert c.set_mode("A1", "ISOLATION") and c.allowed_actions("A1") == ["compute"]
        assert c.set_mode("A1", "FULL_LOCK") and c.allowed_actions("A1") == []
        for bad in (("A1", "OPEN"), ("", "SANDBOX"), (None, "SANDBOX"), ("A1", None)):
            assert c.set_mode(*bad) is False
        assert c.get_mode("A1") == "FULL_LOCK"                                             # a refused call changes nothing
        info = {"owner": {"n": 1}}
        assert c.set_metadata("A1", info) and not c.set_metadata("A1", "text") and not c.set_metadata(None, {})
        assert not c.set_metadata("A1", {"bad": {1, 2}})
    info["owner"]["n"] = 2
    c.get_metadata("A1")["owner"]["n"] = 3
    assert c.get_metadata("A1") == {"owner": {"n": 1}} and c.get_metadata("none") == {}


def test_containment_attempts_are_traced_granted_and_denied():
    c = AgentContainmentModes()
    with acting_as(BOB):
        c.set_mode("A1", "SANDBOX")
    with acting_as(SEC):
        c.set_mode("A1", "SANDBOX")
    acts = [e["action"] for e in trace.entries() if e["actor"] == "access" and e["payload"].get("agent") == "AGENT_CONTAINMENT_MODES"]
    assert acts == ["change.denied", "change.granted"]
