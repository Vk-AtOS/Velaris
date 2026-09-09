from importlib import import_module

AGENTS=[
("CLBPP_CORE","CLBPP_COREAgent"),
("CLBPP_DISTRIBUTOR","CLBPP_DISTRIBUTORAgent"),
("CLBPP_OVERLOAD_MONITOR","CLBPP_OVERLOAD_MONITORAgent"),
("CLBPP_PREDICTIVE_BALANCER","CLBPP_PREDICTIVE_BALANCERAgent")
]

def test_clbpp_health():
    for pkg,cls in AGENTS:
        mod=import_module(f"live.agents.{pkg}.main")
        A=getattr(mod,cls)
        o=A()
        h=o.health_check()
        assert h["status"]=="ok"
        assert h["agent"]==pkg
