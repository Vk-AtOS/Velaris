from importlib import import_module

AGENTS=[
("ASEL_PLANNER","ASEL_PLANNERAgent"),
("ASEL_ROUTER","ASEL_ROUTERAgent"),
("ASEL_EVALUATOR","ASEL_EVALUATORAgent"),
("ASEL_EXECUTOR","ASEL_EXECUTORAgent"),
("ASEL_STRATEGIST","ASEL_STRATEGISTAgent")
]

def test_asel_health():
    for pkg,cls in AGENTS:
        mod=import_module(f"live.agents.{pkg}.main")
        A=getattr(mod,cls)
        o=A()
        h=o.health_check()
        assert h["status"]=="ok"
        assert h["agent"]==pkg
