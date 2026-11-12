from importlib import import_module

def test_csm_health():
    for pkg, cls in [
        ("CSM_CORE","CSMCoreAgent"),
        ("CSM_REASONER","CSMReasonerAgent"),
        ("CSM_LINKER","CSMLinkerAgent"),
        ("CSM_POLICY","CSMPolicyAgent")
    ]:
        mod = import_module(f"agents.{pkg}.main")
        inst = getattr(mod, cls)()
        assert inst.health_check()["status"] == "ok"

def test_csm_ops(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))   # CSM_LINKER now persists its links
    Reasoner = import_module("agents.CSM_REASONER.main").CSMReasonerAgent()
    assert "strategy" in Reasoner.quick_strategy("X")

    Linker = import_module("agents.CSM_LINKER.main").CSMLinkerAgent()
    assert Linker.link("A","B")["linked"] is True

    Policy = import_module("agents.CSM_POLICY.main").CSMPolicyAgent()
    # was `generate_policy("X")["policy"] == "generated"`: the stub "generated" a policy from anything.
    assert Policy.generate_policy({"name": "spend", "required": ["approver"]})["policy"] == "generated"
    assert Policy.generate_policy("X")["policy"] == "rejected"
