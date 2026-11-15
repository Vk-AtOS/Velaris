"""KAN-86: operations agents: path traversal in SKILLPACK_LOADER and the smaller defects."""
import os
from importlib import import_module

import pytest

from velaris.intel.paths import agent_dir


def agent(name, method_marker, *args):
    m = import_module(f"velaris.agents.{name}.main")
    cls = next(v for v in vars(m).values() if isinstance(v, type) and hasattr(v, method_marker) and v.__module__ == m.__name__)
    return cls(*args)


@pytest.mark.parametrize("name", ["../x", "../../escaped", "a/b", "..", ".", "", ".hidden", "x" * 300, None, 5, "a\\b", "a\x00b"])
def test_skillpack_names_cannot_leave_the_folder(name, tmp_path):
    s = agent("SKILLPACK_LOADER", "load_skillpack")
    outside = tmp_path / "victim.json"
    outside.write_text("keep")
    with pytest.raises(ValueError):
        s.load_skillpack(name, {"a": 1})
    with pytest.raises(ValueError):
        s.unload_skillpack(name)
    with pytest.raises(ValueError):
        s.get_skillpack(name)
    assert outside.read_text() == "keep" and not (agent_dir("SKILLPACK_LOADER").parent / "escaped.json").exists()


def test_skillpack_symlink_cannot_be_used_to_delete_elsewhere(tmp_path):
    s = agent("SKILLPACK_LOADER", "load_skillpack")
    victim = tmp_path / "victim.json"
    victim.write_text("keep")
    os.symlink(victim, os.path.join(s.SKILL_DIR, "evil.json"))
    with pytest.raises(ValueError):
        s.unload_skillpack("evil")
    with pytest.raises(ValueError):
        s.load_skillpack("evil", {"a": 1})
    assert victim.read_text() == "keep"


def test_skillpacks_are_private_atomic_and_shared_between_instances():
    s = agent("SKILLPACK_LOADER", "load_skillpack")
    assert s.load_skillpack("pack-1", {"skills": ["a"]}) is True and s.load_skillpack("pack-1", {}) is False
    path = os.path.join(s.SKILL_DIR, "pack-1.json")
    assert oct(os.stat(path).st_mode & 0o777) == "0o600"
    other = agent("SKILLPACK_LOADER", "load_skillpack")
    assert other.get_skillpack("pack-1") == {"skills": ["a"]} and other.list_skillpacks() == ["pack-1"]
    assert other.unload_skillpack("pack-1") is True and s.get_skillpack("pack-1") is None
    with pytest.raises(ValueError):
        s.load_skillpack("big", {"x": "y" * 2_000_000})


def test_connector_layer_does_not_hand_out_its_live_config():
    c = agent("CONNECTOR_LAYER", "get_connector")
    c.register_connector("zoho", {"url": "https://a", "api_key": "SECRET-1", "nested": {"token": "T"}})
    got = c.get_connector("zoho")
    assert got["url"] == "https://a" and got["api_key"] != "SECRET-1" and got["nested"]["token"] != "T"
    got["url"] = "https://evil"
    assert c.get_connector("zoho")["url"] == "https://a"                        # a copy, not the live config
    assert c.request("zoho", {"p": 1})["status"] == "OK"


def test_dynamica_and_tenant_engine_do_not_share_state_with_callers():
    d = agent("DYNAMICA", "evolve_multi", 3) if False else None
    m = import_module("velaris.agents.DYNAMICA.main")
    cls = next(v for v in vars(m).values() if isinstance(v, type) and hasattr(v, "evolve_multi"))
    start = {"x": 1}
    out = cls().evolve_multi(start, lambda st: {"x": st["x"] + 1})
    out[0]["x"] = 99
    assert start == {"x": 1}
    t = agent("MULTI_TENANT_ENGINE", "tenant_snapshot")
    t.create_tenant("a") if hasattr(t, "create_tenant") else None
    t.set_value("a", "cfg", {"deep": [1]})
    snap = t.tenant_snapshot("a")
    snap["cfg"]["deep"].append(2)
    assert t.get_value("a", "cfg") == {"deep": [1]}
    t.get_value("a", "cfg")["deep"].append(3)
    assert t.tenant_snapshot("a")["cfg"] == {"deep": [1]}


def test_codex_unknown_key_counts_as_changed_and_optima_math():
    c = agent("CODEX", "rules_changed")
    assert c.rules_changed("never-stored", {"a": 1}) is True                    # unknown is not "unchanged"
    o = agent("OPTIMA", "pivot_factor")
    assert o.pivot_factor(0.02, 0.04) == pytest.approx(1.0)                     # CTR doubled: +100%, not +0.02
    assert o.pivot_factor(100, 120) == pytest.approx(0.2) and o.pivot_factor(0, 0) == 0.0
    assert o.pivot_factor(0, 5) is None                                         # growth from zero is undefined
    assert o.metric_normalize({"a": -5, "b": -10}) == {"a": -0.5, "b": -1.0}    # signs are kept for a negative max
    assert o.metric_normalize({"a": 5, "b": 10}) == {"a": 0.5, "b": 1.0}
