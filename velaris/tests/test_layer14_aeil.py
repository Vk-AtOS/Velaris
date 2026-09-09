from importlib import import_module

AGENTS=[
("ECON_INTEL_CORE","ECON_INTEL_COREAgent"),
("MARKET_GAP_ANALYZER","MARKET_GAP_ANALYZERAgent"),
("COMPETITIVE_SCANNER","COMPETITIVE_SCANNERAgent"),
("BUSINESS_MODEL_ENGINE","BUSINESS_MODEL_ENGINEAgent"),
("PRICING_OPTIMIZER","PRICING_OPTIMIZERAgent"),
("FEASIBILITY_ENGINE","FEASIBILITY_ENGINEAgent")
]

def test_aeil_health():
    for pkg,cls in AGENTS:
        mod=import_module(f"live.agents.{pkg}.main")
        A=getattr(mod,cls)
        o=A()
        h=o.health_check()
        assert h["status"]=="ok"
        assert h["agent"]==pkg
