"""
Test bootstrap.

Puts the repo root on sys.path and maps the two obsolete package roots that
older tests still import (`agents.X`, `live.agents.X`) onto velaris.agents,
which resolves agents from departments/.
"""
import os
import sys
import types

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import velaris.agents  # noqa: E402  (needs ROOT on sys.path first)

sys.modules.setdefault("agents", velaris.agents)
_live = sys.modules.setdefault("live", types.ModuleType("live"))
_live.__path__ = []
_live.agents = velaris.agents
sys.modules.setdefault("live.agents", velaris.agents)


@pytest.fixture(autouse=True)
def _isolated_velaris_data(monkeypatch, tmp_path_factory):
    """Every test gets its own empty VELARIS_DATA, so no test reads or writes ~/.velaris.

    Tests that set VELARIS_DATA themselves still win: their fixture runs after this one.
    """
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path_factory.mktemp("velaris_data")))
