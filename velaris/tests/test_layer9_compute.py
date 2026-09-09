import importlib

AGENTS = [
    "COMPUTE_KERNEL",
    "DISTRIBUTED_FABRIC",
    "LOCAL_ACCELERATOR",
    "PARALLEL_CORE",
    "STREAM_PROCESSOR",
    "THROUGHPUT_MANAGER",
    "LATENCY_CONTROLLER",
    "SYSTEM_TELEMETRY",
]

def test_compute_agents_health():
    for pkg in AGENTS:
        mod = importlib.import_module(f"agents.{pkg}.main")
        Agent = getattr(mod, f"{pkg}Agent")
        inst = Agent()
        h = inst.health_check()
        assert h["status"] == "ok"

def test_compute_basic_init():
    for pkg in AGENTS:
        mod = importlib.import_module(f"agents.{pkg}.main")
        Agent = getattr(mod, f"{pkg}Agent")
        inst = Agent()
        assert inst.name == pkg
