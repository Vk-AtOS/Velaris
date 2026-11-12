"""ALK family: outcome ledger, bounded parameter adjustment, champion/challenger variants."""
import pytest

from velaris.agents.ALK_ADAPT.main import ALK_ADAPTAgent
from velaris.agents.ALK_EVO.main import ALK_EVOAgent
from velaris.agents.AUTO_LEARN_CORE.main import AUTO_LEARN_COREAgent


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_ledger_ranks_by_confidence_not_raw_rate():
    core = AUTO_LEARN_COREAgent()
    for _ in range(3):
        core.record("reminder", "sms", True)                    # 3/3
    for i in range(100):
        core.record("reminder", "email", i < 90)                # 90/100
    stats = AUTO_LEARN_COREAgent().stats("reminder")["options"]  # new instance: persisted
    assert stats["sms"]["rate"] == 1.0 and stats["email"]["rate"] == 0.9
    assert stats["email"]["lower_bound"] > stats["sms"]["lower_bound"]
    r = core.best("reminder", ["sms", "email", "letter"])
    assert r["choice"] == "email" and r["untried"] == ["letter"]
    assert [x["option"] for x in r["ranking"]] == ["email", "sms", "letter"]


def test_ledger_no_data_and_bad_input():
    core = AUTO_LEARN_COREAgent()
    r = core.best("unknown", ["a", "b"])
    assert r["status"] == "no_data" and r["choice"] is None and r["untried"] == ["a", "b"]
    core.record("ctx", "bad", False)
    assert [x["option"] for x in core.best("ctx", ["bad", "new"], min_trials=0)["ranking"]] == ["new", "bad"]
    assert core.record("ctx", "a", "yes")["status"] == "invalid_input"
    assert core.record("", "a", True)["status"] == "invalid_input"
    assert core.best("ctx", "a")["status"] == "invalid_input"
    assert core.stats(None)["options"] == {}


def test_adapt_moves_toward_target_within_limits():
    a = ALK_ADAPTAgent()
    # raising the auto-approval limit lowers the manual-review rate: direction -1
    assert a.define("auto_approve_limit", 1000, low=500, high=1500, max_step=200, direction=-1)["status"] == "ok"
    r = a.adapt("auto_approve_limit", observed=0.35, target=0.20, gain=1000, now=1)
    assert r["value"] == 1150 and r["limited_by"] is None        # -1 * 1000 * (0.20 - 0.35) = +150
    r = a.adapt("auto_approve_limit", observed=0.90, target=0.20, gain=1000, now=2)
    assert r["value"] == 1350 and r["limited_by"] == "max_step"  # wanted +700, capped at 200
    r = ALK_ADAPTAgent().adapt("auto_approve_limit", 0.90, 0.20, gain=1000, now=3)
    assert r["value"] == 1500 and r["limited_by"] == "max_step"
    r = a.adapt("auto_approve_limit", 0.25, 0.20, gain=1000, now=4)
    assert r["value"] == 1500 and r["limited_by"] == "bound" and r["change"] == 0
    assert a.adapt("auto_approve_limit", 0.05, 0.20, gain=1000, now=5)["value"] == 1350
    assert len(a.get("auto_approve_limit")["history"]) == 5


def test_adapt_bad_input():
    a = ALK_ADAPTAgent()
    assert a.define("p", 5, low=10, high=20, max_step=1)["status"] == "invalid_input"
    assert a.define("p", 5, 0, 10, max_step=0)["status"] == "invalid_input"
    assert a.define("p", 5, 0, 10, 1, direction=0)["status"] == "invalid_input"
    assert a.adapt("missing", 1, 2)["status"] == "not_found"
    a.define("p", 5, 0, 10, 1)
    assert a.adapt("p", "high", 2)["status"] == "invalid_input"
    assert a.adapt("p", 1, 2, gain=0)["status"] == "invalid_input"
    assert a.get("p")["value"] == 5 and a.get("nope")["status"] == "not_found"


def test_evo_promotes_only_on_evidence_and_rolls_back():
    evo = ALK_EVOAgent(min_samples=3, margin=0.05)
    evo.register("v1", {"subject": "Invoice due"})
    evo.register("v2", {"subject": "Friendly reminder"})
    assert evo.register("v2", {})["status"] == "duplicate"
    for s in (0.50, 0.52, 0.48):
        evo.record("v1", s)
    evo.record("v2", 0.99)
    r = evo.evaluate()
    assert r["promoted"] is False and r["champion"] == "v1" and "lack samples" in r["reason"]
    evo.record("v2", 0.53)
    evo.record("v2", 0.10)                                        # mean 0.54: better, but inside the margin
    assert evo.evaluate()["reason"] == "no challenger beats the champion by the margin"
    for s in (0.9, 0.9, 0.9):
        evo.record("v2", s)
    won = ALK_EVOAgent(min_samples=3, margin=0.05).evaluate()     # new instance
    assert won["promoted"] is True and won["champion"] == "v2" and won["replaced"] == "v1"
    assert evo.champion()["config"] == {"subject": "Friendly reminder"}
    assert evo.rollback()["champion"] == "v1"
    assert evo.rollback()["status"] == "not_found"


def test_evo_bad_input():
    evo = ALK_EVOAgent()
    assert evo.champion()["status"] == "not_found" and evo.evaluate()["status"] == "not_found"
    assert evo.register("", {})["status"] == "invalid_input"
    assert evo.register("v1", "config")["status"] == "invalid_input"
    assert evo.record("ghost", 1)["status"] == "not_found"
    evo.register("v1", {})
    assert evo.record("v1", "good")["status"] == "invalid_input"
    assert evo.evaluate()["promoted"] is False
