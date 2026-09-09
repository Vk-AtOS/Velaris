from importlib import import_module

AGENTS=[
("CRK_REASONER","CRK_REASONERAgent"),
("CRK_CHAIN","CRK_CHAINAgent"),
("CRK_CONTEXT","CRK_CONTEXTAgent"),
("CRK_INTENT","CRK_INTENTAgent"),
("CRK_VALIDATOR","CRK_VALIDATORAgent")
]

def test_crk_health():
    for pkg,cls in AGENTS:
        mod=import_module(f"live.agents.{pkg}.main")
        A=getattr(mod,cls)
        o=A()
        h=o.health_check()
        assert h["status"]=="ok"
        assert h["agent"]==pkg
