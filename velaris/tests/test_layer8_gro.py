import importlib

AGENTS = [
    "RESOURCE_ORCHESTRATOR",
    "LOAD_DISTRIBUTOR",
    "COMPUTE_SCALER",
    "MEMORY_REALLOCATOR",
    "NETWORK_OPTIMIZER",
    "ENERGY_MANAGER",
    "FAILOVER_ROUTER",
    "GLOBAL_STATE_MAP",
]

def test_gro_agents_health():
    for pkg in AGENTS:
        mod = importlib.import_module(f"agents.{pkg}.main")
        Agent = getattr(mod, f"{pkg}Agent")
        inst = Agent()
        h = inst.health_check()
        assert h["status"] == "ok"

def test_gro_basic_init():
    for pkg in AGENTS:
        mod = importlib.import_module(f"agents.{pkg}.main")
        Agent = getattr(mod, f"{pkg}Agent")
        inst = Agent()
        assert inst.name == pkg
