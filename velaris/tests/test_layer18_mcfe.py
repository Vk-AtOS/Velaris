from importlib import import_module

def test_mcfe_health():
    for pkg, cls in [
        ("MCFE_CORE","MCFECoreAgent"),
        ("MCFE_CLASSIFIER","MCFEClassifierAgent"),
        ("MCFE_ROUTER","MCFERouterAgent"),
        ("MCFE_FIELDGEN","MCFEFieldGenAgent")
    ]:
        mod = import_module(f"agents.{pkg}.main")
        inst = getattr(mod, cls)()
        assert inst.health_check()["status"] == "ok"

def test_mcfe_ops():
    Classifier = import_module("agents.MCFE_CLASSIFIER.main").MCFEClassifierAgent()
    domain = Classifier.classify("example")["domain"]

    Router = import_module("agents.MCFE_ROUTER.main").MCFERouterAgent()
    assert Router.route(domain)["route"] == "ok"

    Field = import_module("agents.MCFE_FIELDGEN.main").MCFEFieldGenAgent()
    assert Field.generate_field(domain)["field"] == "generated"
