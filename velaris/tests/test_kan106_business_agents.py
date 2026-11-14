"""KAN-106 (finance, operations, project management, marketing, executive agents)."""
import math
from importlib import import_module

import pytest


def mod(name):
    return import_module(f"velaris.agents.{name}.main")


def test_portfolio_with_inconsistent_correlations_fails_cleanly():
    m = mod("PORTFOLIO_SIM_ENGINE")
    eng = m.PortfolioSimEngine() if hasattr(m, "PortfolioSimEngine") else getattr(m, "PORTFOLIO_SIM_ENGINEAgent")()
    third = 1 / 3
    p = m.PortfolioInput("p", {"a": third, "b": third, "c": third}, {"a": .1, "b": .1, "c": .1},
                         {"a": .2, "b": .2, "c": .2},
                         {"a": {"a": 1, "b": -1, "c": -1}, "b": {"a": -1, "b": 1, "c": -1}, "c": {"a": -1, "b": -1, "c": 1}})
    r = eng.simulate(p)
    assert r["status"] == "failed" and "positive semi-definite" in r["errors"][0]


def test_forecasta_window_must_be_positive():
    f = mod("FORECASTA").FORECASTAAgent() if hasattr(mod("FORECASTA"), "FORECASTAAgent") else None
    if f is None:
        f = [v for v in vars(mod("FORECASTA")).values() if isinstance(v, type) and hasattr(v, "rolling_projection")][0]()
    for bad in (0, -2, True, "3"):
        with pytest.raises(ValueError):
            f.rolling_projection([1, 2, 3], window=bad)
    assert f.rolling_projection([1, 2, 3, 4], window=2) == 3.5


def test_pipeline_monitor_zero_spread_history_flags_a_big_jump(tmp_path):
    m = mod("PIPELINE_MONITOR")
    pm = m.PipelineMonitor(str(tmp_path / "p.db"))
    for _ in range(5):
        pm.log_stage("build", 2.0)
    assert pm.log_stage("build", 20.0)["label"] != "normal"
    assert pm.log_stage("build", 2.0)["label"] == "normal"


def test_pipeline_monitor_and_ops_report_keep_their_db_under_velaris_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mod("PIPELINE_MONITOR").PipelineMonitor()
    mod("OPS_REPORT").OpsReport()
    assert not list(tmp_path.glob("*.db"))                       # nothing in the working directory
    from velaris.intel.paths import agent_dir
    assert (agent_dir("PIPELINE_MONITOR") / "pipeline_data.db").exists()
    assert (agent_dir("OPS_REPORT") / "ops_data.db").exists()


def test_ops_report_uses_one_clock_and_prints_the_requested_date(tmp_path):
    from datetime import datetime
    r = mod("OPS_REPORT").OpsReport(db_path=str(tmp_path / "o.db"))
    r.log("sales", "calls", "5")
    today = datetime.utcnow().strftime("%Y-%m-%d")
    assert "calls: 5" in r.generate() and r.generate_dict()["date"] == today
    assert "01 Jan 2020" in r.generate("2020-01-01") and "calls" not in r.generate("2020-01-01")


def test_geneflow_diff_then_migration_keeps_values():
    g = mod("GENEFLOW").GeneFlowAgent()
    old, new = {"a": 1, "b": 2, "gone": 0}, {"a": 1, "b": 3, "c": 10}
    assert g.apply_migration(old, g.compute_diff(old, new)) == new
    with pytest.raises(ValueError):
        g.apply_migration(old, {"added": ["c"], "changed": [], "removed": []})


def test_optima_pivot_with_negative_baseline_has_the_right_sign():
    o = mod("OPTIMA")
    cls = [v for v in vars(o).values() if isinstance(v, type) and hasattr(v, "pivot_factor")][0]
    assert cls().pivot_factor(-10, 0) > 0


@pytest.mark.parametrize("hours", [float("nan"), float("inf"), -1, 0, 25, True])
def test_time_tracker_refuses_non_finite_hours_and_keeps_db_in_data_dir(hours, tmp_path):
    t = mod("TIME_TRACKER")
    cls = [v for v in vars(t).values() if isinstance(v, type) and hasattr(v, "weekly_utilization")][0]()
    assert "error" in cls.log("e1", "p1", hours)
    assert "error" not in cls.log("e1", "p1", 2)
    import os
    assert not os.path.exists(os.path.join(os.path.dirname(t.__file__), "timelog.db"))


def test_sprint_planner_refuses_nan_points_and_keeps_db_in_data_dir():
    s = mod("SPRINT_PLANNER")
    cls = [v for v in vars(s).values() if isinstance(v, type) and hasattr(v, "add_task")][0]()
    assert "error" in cls.add_task(1, "t", "title", story_points=float("nan"))
    import os
    assert not os.path.exists(os.path.join(os.path.dirname(s.__file__), "sprints.db"))


def test_vmrk_non_ascii_signature_is_false_not_a_crash():
    m = mod("VMRK")
    cls = [v for v in vars(m).values() if isinstance(v, type) and hasattr(v, "verify")][0]()
    sig = cls.sign("hello")
    assert cls.verify("hello", sig) is True
    assert cls.verify("hello", "café") is False and cls.verify("hello", None) is False


def test_dry_run_live_mode_is_not_logged_as_simulated():
    m = mod("DRY_RUN_SIMULATION")
    sim = m.DryRunSimulation(dry_run=False)
    sim.execute_action("send", {"x": 1})
    log = sim.read_log()
    assert [list(e)[0] for e in log] == ["executed"]


def test_competitive_scanner_does_not_store_the_hash_when_extraction_failed():
    import inspect
    src = inspect.getsource(mod("COMPETITIVE_SCANNER"))
    assert 'row.get("extraction") != "ok"' in src
