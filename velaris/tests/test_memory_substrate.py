from importlib import import_module

AGENTS = [
    ("MEMORY_MESH", "MEMORY_MESHAgent"),
    ("MEMORY_FABRIC", "MEMORY_FABRICAgent"),
    ("SHORTTERM_MEMORY", "SHORTTERM_MEMORYAgent"),
    ("LONGTERM_MEMORY", "LONGTERM_MEMORYAgent"),
    ("EPISODIC_MEMORY", "EPISODIC_MEMORYAgent"),
    ("OFFLINE_REGISTRY", "OFFLINE_REGISTRYAgent"),
    ("MEMORY_CLOUD_EXPAND", "MEMORY_CLOUD_EXPANDAgent"),
]

def test_memory_agents_health():
    for pkg, cls in AGENTS:
        mod = import_module(f"live.agents.{pkg}.main")
        Agent = getattr(mod, cls)
        inst = Agent()
        h = inst.health_check()
        assert isinstance(h, dict)
        assert h.get("status") == "ok"

def test_memory_basic_ops(tmp_path):
    # Shortterm push/pop
    short = import_module("live.agents.SHORTTERM_MEMORY.main").SHORTTERM_MEMORYAgent()
    short.push({"t":"x"})
    assert len(short.recent(5)) >= 1

    longp = tmp_path / "lt.json"
    long = import_module("live.agents.LONGTERM_MEMORY.main").LONGTERM_MEMORYAgent(str(longp))
    long.put("k1", {"v":1})
    assert long.get("k1") == {"v":1}

    episodic = import_module("live.agents.EPISODIC_MEMORY.main").EPISODIC_MEMORYAgent()
    episodic.record({"e":"ep"})
    assert episodic.list_episodes()[-1]["e"] == "ep"

    mesh = import_module("live.agents.MEMORY_MESH.main").MEMORY_MESHAgent()
    mesh.register_node("n1", {"meta":"ok"})
    assert "n1" in mesh.nodes()

    fabric = import_module("live.agents.MEMORY_FABRIC.main").MEMORY_FABRICAgent()
    fabric.write_bucket("b1", {"x":1})
    assert fabric.read_bucket("b1") == {"x":1}

    offline = import_module("live.agents.OFFLINE_REGISTRY.main").OFFLINE_REGISTRYAgent(str(tmp_path/"reg.json"))
    offline.set("foo","bar")
    assert offline.get("foo") == "bar"

    cloud = import_module("live.agents.MEMORY_CLOUD_EXPAND.main").MEMORY_CLOUD_EXPANDAgent()
    cloud.sync_meta({"k":"v"})
    assert cloud.meta()["k"] == "v"
