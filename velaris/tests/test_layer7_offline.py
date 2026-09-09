from importlib import import_module

def test_health():
    modules = [
        "LOCAL_AUTONOMY_CORE","LOCAL_REGISTRY_CACHE","LOCAL_MEMORY_STORE",
        "LOCAL_EMBEDDING_ENGINE","LOCAL_ROUTER","OFFLINE_EXECUTION_ENGINE",
        "RESOURCE_OPTIMIZER","OFFLINE_SANDBOX","CLOUD_HANDOFF_CONTROLLER"
    ]
    for pkg in modules:
        mod = import_module(f"live.agents.{pkg}.main")
        Agent = [a for a in dir(mod) if a.lower().startswith(pkg.lower()) or a.lower().endswith("engine") or a.lower().endswith("core")]
        obj = getattr(mod, [c for c in dir(mod) if c[0].isupper()][0])()
        assert obj.health_check()["status"] == "ok"
