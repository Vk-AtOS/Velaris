from importlib import import_module

def test_acf_health():
    for pkg, cls in [
        ("ACF_CORE","ACFCoreAgent"),
        ("ACF_ROUTER","ACFRouterAgent"),
        ("ACF_FUSION","ACFFusionAgent"),
        ("ACF_CONTEXT","ACFContextAgent")
    ]:
        mod = import_module(f"agents.{pkg}.main")
        inst = getattr(mod, cls)()
        assert inst.health_check()["status"] == "ok"

def test_acf_ops():
    Router = import_module("agents.ACF_ROUTER.main").ACFRouterAgent()
    assert Router.route("SIG")["routed"] is True

    Fusion = import_module("agents.ACF_FUSION.main").ACFFusionAgent()
    assert Fusion.fuse("A","B")["fusion"] is True

    Context = import_module("agents.ACF_CONTEXT.main").ACFContextAgent()
    assert Context.contextualize("X")["contextualized"] is True
