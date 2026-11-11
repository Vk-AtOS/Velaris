import importlib

# X_SIM moved to _archived_domains/research_simulation; see _archived_tests/test_removed_cases.py
ALIASES = [
"CRK","ASEL","AEIL","SANDE","SAGE","NIRVANA",
"HYPERSYNC","CORE_CONVERGENCE","FSCL","GCK","CONVERGENCE_BRIDGE"
]

def test_alias_imports_and_health():
    for a in ALIASES:
        mod = importlib.import_module(f"agents.{a}.main")
        cls = None
        for attr in dir(mod):
            if attr.upper().endswith("AGENT"):
                cls = getattr(mod, attr)
                break
        assert cls is not None
        inst = cls()
        h = inst.health_check()
        assert isinstance(h, dict)
        assert "agent" in h
