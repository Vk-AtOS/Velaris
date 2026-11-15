from importlib import import_module

def test_health():
    modules = [
        "LOCAL_AUTONOMY_CORE","LOCAL_REGISTRY_CACHE","LOCAL_MEMORY_STORE",
        "LOCAL_EMBEDDING_ENGINE","LOCAL_ROUTER","OFFLINE_EXECUTION_ENGINE",
        "RESOURCE_OPTIMIZER","OFFLINE_SANDBOX","CLOUD_HANDOFF_CONTROLLER"
    ]
    for pkg in modules:
        mod = import_module(f"live.agents.{pkg}.main")
        # was "first capitalised name in dir(mod)", which picks typing.Any once a module imports it;
        # now: the class defined in that module that has a health_check
        cls = next(v for v in vars(mod).values()
                   if isinstance(v, type) and v.__module__ == mod.__name__ and hasattr(v, "health_check"))
        obj = cls()
        assert obj.health_check()["status"] == "ok"
