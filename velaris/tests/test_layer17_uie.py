from importlib import import_module

def test_uie_health():
    for pkg, cls in [
        ("UIE_CORE","UIECoreAgent"),
        ("UIE_REASONER","UIEReasonerAgent"),
        ("UIE_SEMANTICS","UIESemanticsAgent"),
        ("UIE_SIGNAL","UIESignalAgent")
    ]:
        mod = import_module(f"agents.{pkg}.main")
        inst = getattr(mod, cls)()
        assert inst.health_check()["status"] == "ok"

def test_uie_ops():
    R = import_module("agents.UIE_REASONER.main").UIEReasonerAgent()
    assert R.reason("X")["reasoned"] is True

    S = import_module("agents.UIE_SEMANTICS.main").UIESemanticsAgent()
    assert S.interpret("Y")["interpreted"] is True

    Sig = import_module("agents.UIE_SIGNAL.main").UIESignalAgent()
    assert Sig.process("SIG")["processed"] is True
