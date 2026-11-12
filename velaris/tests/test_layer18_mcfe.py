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
    result = Classifier.classify("example")
    # was `status == "not_implemented"`: the classifier now counts each domain's terms; "example" has none,
    # so it is undecided (domain None) rather than a guess
    assert result["status"] == "no_match"
    domain = result["domain"]
    assert domain is None
    assert Classifier.classify("invoice payment overdue")["domain"] == "finance"

    # was `route == "ok"` and `field == "generated"` for a None domain (echo stubs); an unknown domain
    # now goes to a person and gets no field list
    Router = import_module("agents.MCFE_ROUTER.main").MCFERouterAgent()
    assert Router.route(domain)["route"] == "unrouted"
    assert Router.route("finance")["route"] == "ok"

    Field = import_module("agents.MCFE_FIELDGEN.main").MCFEFieldGenAgent()
    assert Field.generate_field(domain)["field"] is None
    assert Field.generate_field("finance")["field"] == "generated"
