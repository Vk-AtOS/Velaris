"""KAN-45: the eval runner scores every agent's eval set, marks an agent ready only for a real model, and publishes the table."""
import importlib.util
import json
from pathlib import Path

from velaris.intel.llm import FakeLLM

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("eval_runner", ROOT / "tools" / "eval_runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_offline_run_scores_everything_and_marks_nothing_ready():
    rows = runner.run_all(None, departments=["executive"])
    assert len(rows) == 12 and all(r["rate"] == 1.0 and r["ready"] is False for r in rows.values())


def test_a_model_that_misuses_tools_fails_cases_and_is_not_ready():
    bad = FakeLLM(lambda p, m: '{"tool": "no_such_tool", "args": {}}')
    rows = runner.run_all("fake:m", agents=["ORACLE", "INSIGHTA"], llm=bad)
    assert all(r["rate"] < 0.9 and r["ready"] is False and r["failed"] for r in rows.values())


def test_ready_needs_a_real_model_name_and_the_threshold():
    says_cannot = FakeLLM(lambda p, m: '{"final": "I cannot do that."}')
    rows = runner.run_all("fake:m", agents=["ORACLE"], threshold=0.0, llm=says_cannot)
    assert rows["ORACLE"]["ready"] is True               # threshold 0 and a model given
    assert runner.run_all("fake:m", agents=["ORACLE"], threshold=0.9, llm=says_cannot)["ORACLE"]["ready"] is False


def test_the_table_and_files_are_published(tmp_path):
    assert runner.main(["--departments", "executive", "--out-dir", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "fake-oracle.json").read_text())
    assert data["model"] == "fake:oracle" and len(data["agents"]) == 12
    table = (tmp_path / "fake-oracle.md").read_text()
    assert "| executive | 12 | 12 |" in table and "no agent is LLM-ready" in table


def test_an_agent_without_an_eval_set_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "eval_path", lambda d, a: tmp_path / "missing.json")
    assert runner.run_all(None, agents=["ORACLE"])["ORACLE"] == {"department": "executive", "error": "no eval set"}
