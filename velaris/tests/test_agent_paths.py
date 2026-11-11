"""Agents that keep state on disk keep it under VELARIS_DATA, not a fixed /live path."""
import importlib
import inspect
import os

import pytest

STATEFUL_AGENTS = [
    "MODEL_REGISTRY_CANARY", "AUTONOMOUS_PATCH_ENGINE", "HFAL", "SECRETS_VAULT",
    "SIGNED_AUDIT_CHAIN", "DEEP_AUDIT_ENGINE", "IDENTITY_FRAMEWORK", "SECURE_ACTION_TOKENS",
    "OFFLINE_RUNTIME_PACKAGER", "TELEMETRY_SPINE", "DRY_RUN_SIMULATION", "ROLLBACK_ENGINE",
    "TEMPORAL_SNAPSHOTS", "MEMORY_DRIFT_DETECTOR", "SKILLPACK_LOADER", "VMRK",
]


def _agent_class(name):
    module = importlib.import_module(f"velaris.agents.{name}.main")
    classes = [c for _, c in inspect.getmembers(module, inspect.isclass) if c.__module__ == module.__name__]
    assert len(classes) == 1, classes
    return classes[0]


@pytest.mark.parametrize("name", STATEFUL_AGENTS)
def test_agent_state_lives_under_velaris_data(name, tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    agent = _agent_class(name)()
    home = tmp_path / "agents" / name
    assert home.is_dir()
    paths = [v for v in vars(agent).values() if isinstance(v, str) and os.sep in v]
    assert paths, "agent exposes no path attributes"
    for p in paths:
        assert p.startswith(str(home)), p
        assert not p.startswith("/live/")


def test_signed_state_survives_a_second_instance(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    vmrk = _agent_class("VMRK")
    signature = vmrk().sign("hello")
    assert vmrk().verify("hello", signature)  # same key file is found again
