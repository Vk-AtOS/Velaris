from importlib import import_module

# The other five layer-6 agents (and the pipeline test that chained all eight)
# were removed with the research_simulation archive (git tag archive/pre-reorg).
AGENTS = [
    ("CAUSALITY_RESOLVER","CausalityResolver"),
    ("HYPERSTATE_SYNTHESIZER","HyperstateSynthesizer"),
    ("DECISION_COLLAPSE_ENGINE","DecisionCollapseEngine"),
]

def test_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"live.agents.{pkg}.main")
        Agent = getattr(mod, cls)
        assert Agent().health_check()["status"] == "ok"
