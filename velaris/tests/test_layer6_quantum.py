from importlib import import_module

# The other five layer-6 agents (and the pipeline test that chained all eight)
# moved to _archived_domains/research_simulation; their tests are in
# _archived_tests/test_layer6_quantum.py.
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
