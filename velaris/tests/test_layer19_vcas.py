from importlib import import_module

import pytest


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))   # these agents now keep state; never write to ~/.velaris

def test_vcas_health():
    for pkg, cls in [
        ("VCAS_CORE","VCASCoreAgent"),
        ("VCAS_ROUTER","VCASRouterAgent"),
        ("VCAS_AUTOPILOT","VCASAutopilotAgent"),
        ("VCAS_SUPERVISOR","VCASSupervisorAgent")
    ]:
        mod = import_module(f"agents.{pkg}.main")
        inst = getattr(mod, cls)()
        assert inst.health_check()["status"] == "ok"

def test_vcas_ops():
    # was `autopilot_route == "ok"` and `executed is True` for the bare string "TASK" (echo stubs). A task is
    # now an object; one with no registered handler goes to a person and nothing runs without a recorded approval.
    R = import_module("agents.VCAS_ROUTER.main").VCASRouterAgent()
    assert R.route("TASK")["autopilot_route"] == "manual"

    A = import_module("agents.VCAS_AUTOPILOT.main").VCASAutopilotAgent()
    assert A.execute("TASK")["executed"] is False

    S = import_module("agents.VCAS_SUPERVISOR.main").VCASSupervisorAgent()
    assert S.approve("TASK")["approved"] is False  # was `is True`: the stub approved everything; it now denies (fail closed)
