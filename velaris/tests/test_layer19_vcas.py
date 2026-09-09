from importlib import import_module

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
    R = import_module("agents.VCAS_ROUTER.main").VCASRouterAgent()
    assert R.route("TASK")["autopilot_route"] == "ok"

    A = import_module("agents.VCAS_AUTOPILOT.main").VCASAutopilotAgent()
    assert A.execute("TASK")["executed"] is True

    S = import_module("agents.VCAS_SUPERVISOR.main").VCASSupervisorAgent()
    assert S.approve("TASK")["approved"] is True
