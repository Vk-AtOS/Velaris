"""KAN-113: every database/JSON an agent writes lives under VELARIS_DATA, never in the source tree or the cwd."""
import importlib
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _make(agent, cls, *a):
    return getattr(importlib.import_module(f"velaris.agents.{agent}.main"), cls)(*a)


CASES = [("hr", "RECRUITMENT_ATS", "RecruitmentATSAgent"), ("hr", "EMPLOYEE_ONBOARDING", "EmployeeOnboardingAgent"),
         ("operations", "SLA_MONITOR", "SLAMonitorAgent"), ("operations", "PIPELINE_MONITOR", "PipelineMonitorAgent"),
         ("operations", "OPS_REPORT", "OpsReportAgent"), ("sales", "WHATSAPP_BRIEFING", "WhatsAppBriefingAgent"),
         ("it_infrastructure", "OFFLINE_REGISTRY", "OFFLINE_REGISTRYAgent"), ("data_knowledge", "LONGTERM_MEMORY", "LONGTERM_MEMORYAgent"),
         ("communications", "CALL_RECORDER", "CallRecorder")]


@pytest.mark.parametrize("dept,agent,cls", CASES)
def test_agent_data_goes_under_velaris_data(dept, agent, cls, tmp_path, monkeypatch):
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    monkeypatch.chdir(cwd)
    before = {p for p in ROOT.rglob("*.db")}
    _make(agent, cls)
    assert not list(cwd.iterdir()) and {p for p in ROOT.rglob("*.db")} == before
    assert any(Path(os.environ["VELARIS_DATA"]).rglob("*")), "nothing created under VELARIS_DATA"


def test_module_level_sqlite_agents_resolve_the_path_at_use():
    for dept, agent in [("hr", "LEAVE_MANAGEMENT"), ("hr", "PERFORMANCE_REVIEW_ENGINE"), ("project_management", "TIME_TRACKER"),
                        ("project_management", "SPRINT_PLANNER"), ("communications", "MEETING_SUMMARIZER"),
                        ("communications", "ACTION_ITEM_EXTRACTOR")]:
        src = (ROOT / "departments" / dept / agent / "main.py").read_text()
        # a module-level _DB may only be the empty override sentinel; the real path is resolved when the agent runs
        assert ("_DB =" not in src or '_DB = ""' in src) and ("agent_file(" in src or "agent_dir(" in src), agent


def test_a_file_in_the_working_directory_is_never_adopted_into_an_agent_store(tmp_path, monkeypatch):
    """KAN-69 SV2-14: legacy adoption used to copy <cwd>/<filename> into the agent store."""
    from velaris.intel import paths
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    (cwd / "memory.db").write_bytes(b"planted")
    monkeypatch.chdir(cwd)
    assert cwd / "memory.db" not in paths.legacy_candidates("ANY_AGENT", "memory.db")
